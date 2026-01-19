"""
字幕解析模块 - 支持 SRT 和 ASS 格式的解析与写出

Subtitle Dataclass:
    - index: int       字幕序号
    - start: str       开始时间
    - end: str         结束时间
    - text: str        字幕文本
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


@dataclass
class Subtitle:
    """字幕数据类"""
    index: int
    start: str
    end: str
    text: str
    # ASS 格式额外属性
    style: str = "Default"
    name: str = ""
    margin_l: int = 0
    margin_r: int = 0
    margin_v: int = 0
    effect: str = ""


@dataclass
class ASSMetadata:
    """ASS 文件元数据"""
    script_info: List[str] = field(default_factory=list)
    styles: List[str] = field(default_factory=list)
    events_header: str = ""


def parse_srt(file_path: str) -> List[Subtitle]:
    """
    解析 SRT 字幕文件
    
    Args:
        file_path: SRT 文件路径
        
    Returns:
        字幕列表
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 移除 BOM
    content = content.lstrip('\ufeff')
    
    # 按空行分割字幕块
    blocks = re.split(r'\n\s*\n', content.strip())
    subtitles = []
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
            
        try:
            index = int(lines[0].strip())
        except ValueError:
            continue
            
        # 解析时间轴
        time_match = re.match(
            r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})',
            lines[1].strip()
        )
        if not time_match:
            continue
            
        start = time_match.group(1)
        end = time_match.group(2)
        text = '\n'.join(lines[2:])
        
        subtitles.append(Subtitle(
            index=index,
            start=start,
            end=end,
            text=text
        ))
    
    return subtitles


def write_srt(subtitles: List[Subtitle], output_path: str) -> None:
    """
    写出 SRT 字幕文件
    
    Args:
        subtitles: 字幕列表
        output_path: 输出文件路径
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, sub in enumerate(subtitles, 1):
            f.write(f"{i}\n")
            f.write(f"{sub.start} --> {sub.end}\n")
            f.write(f"{sub.text}\n\n")


def parse_vtt(file_path: str) -> List[Subtitle]:
    """
    解析 VTT (WebVTT) 字幕文件
    
    Args:
        file_path: VTT 文件路径
        
    Returns:
        字幕列表
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 移除 BOM
    content = content.lstrip('\ufeff')
    
    # 检查 WEBVTT 头
    if not content.strip().startswith('WEBVTT'):
        raise ValueError("无效的 VTT 文件: 缺少 WEBVTT 头")
    
    # 按空行分割块
    blocks = re.split(r'\n\s*\n', content.strip())
    subtitles = []
    index = 0
    
    for block in blocks[1:]:  # 跳过 WEBVTT 头块
        lines = block.strip().split('\n')
        if not lines:
            continue
        
        # 跳过 STYLE, REGION, NOTE 块
        first_line = lines[0].strip().upper()
        if first_line.startswith('STYLE') or first_line.startswith('REGION') or first_line.startswith('NOTE'):
            continue
        
        # 查找时间轴行
        time_line_idx = 0
        for i, line in enumerate(lines):
            if '-->' in line:
                time_line_idx = i
                break
        else:
            continue  # 没有时间轴，跳过此块
        
        # 解析时间轴 (格式: HH:MM:SS.mmm --> HH:MM:SS.mmm 或 MM:SS.mmm --> MM:SS.mmm)
        time_match = re.match(
            r'(\d{1,2}:)?\d{2}:\d{2}\.\d{3}\s*-->\s*(\d{1,2}:)?\d{2}:\d{2}\.\d{3}',
            lines[time_line_idx].strip()
        )
        if not time_match:
            continue
        
        # 提取开始和结束时间
        time_parts = lines[time_line_idx].split('-->')
        start_vtt = time_parts[0].strip().split()[0]  # 移除可能的 cue settings
        end_vtt = time_parts[1].strip().split()[0]
        
        # 转换为 SRT 格式时间
        start = _vtt_time_to_srt(start_vtt)
        end = _vtt_time_to_srt(end_vtt)
        
        # 提取文本（时间轴之后的所有行）
        text = '\n'.join(lines[time_line_idx + 1:])
        
        # 移除 VTT 样式标签（如 <c>, <b>, <i> 等）
        text = re.sub(r'<[^>]+>', '', text)
        
        index += 1
        subtitles.append(Subtitle(
            index=index,
            start=start,
            end=end,
            text=text
        ))
    
    return subtitles


def write_vtt(subtitles: List[Subtitle], output_path: str) -> None:
    """
    写出 VTT (WebVTT) 字幕文件
    
    Args:
        subtitles: 字幕列表
        output_path: 输出文件路径
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("WEBVTT\n\n")
        
        for sub in subtitles:
            # 转换时间格式
            start_vtt = _srt_time_to_vtt(sub.start)
            end_vtt = _srt_time_to_vtt(sub.end)
            
            f.write(f"{sub.index}\n")
            f.write(f"{start_vtt} --> {end_vtt}\n")
            f.write(f"{sub.text}\n\n")


def _vtt_time_to_srt(vtt_time: str) -> str:
    """将 VTT 时间格式转换为 SRT 时间格式
    
    VTT: (HH:)MM:SS.mmm
    SRT: HH:MM:SS,mmm
    """
    # 处理可能没有小时的情况
    parts = vtt_time.split(':')
    if len(parts) == 2:
        # MM:SS.mmm 格式
        m, s_ms = parts
        h = '00'
    else:
        # HH:MM:SS.mmm 格式
        h, m, s_ms = parts
    
    # 将 . 替换为 ,
    s_ms = s_ms.replace('.', ',')
    
    return f"{int(h):02d}:{m}:{s_ms}"


def _srt_time_to_vtt(srt_time: str) -> str:
    """将 SRT 时间格式转换为 VTT 时间格式
    
    SRT: HH:MM:SS,mmm
    VTT: HH:MM:SS.mmm
    """
    return srt_time.replace(',', '.')


def parse_ass(file_path: str) -> tuple[List[Subtitle], ASSMetadata]:
    """
    解析 ASS 字幕文件
    
    Args:
        file_path: ASS 文件路径
        
    Returns:
        (字幕列表, ASS 元数据)
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 移除 BOM
    content = content.lstrip('\ufeff')
    
    metadata = ASSMetadata()
    subtitles = []
    
    current_section = None
    dialogue_format = []
    
    for line in content.split('\n'):
        line = line.strip()
        
        # 检测 section
        if line.startswith('[') and line.endswith(']'):
            current_section = line[1:-1].lower()
            if current_section == 'script info':
                metadata.script_info.append(line)
            elif current_section in ['v4 styles', 'v4+ styles']:
                metadata.styles.append(line)
            continue
        
        if current_section == 'script info':
            metadata.script_info.append(line)
        elif current_section in ['v4 styles', 'v4+ styles']:
            metadata.styles.append(line)
        elif current_section == 'events':
            if line.startswith('Format:'):
                metadata.events_header = line
                format_parts = line[7:].split(',')
                dialogue_format = [p.strip().lower() for p in format_parts]
            elif line.startswith('Dialogue:'):
                parts = line[9:].split(',', len(dialogue_format) - 1)
                if len(parts) >= len(dialogue_format):
                    sub_dict = dict(zip(dialogue_format, parts))
                    
                    # 转换时间格式
                    start = _ass_time_to_srt(sub_dict.get('start', '0:00:00.00'))
                    end = _ass_time_to_srt(sub_dict.get('end', '0:00:00.00'))
                    text = sub_dict.get('text', '').replace('\\N', '\n').replace('\\n', '\n')
                    
                    # 移除 ASS 样式标签
                    text = re.sub(r'\{[^}]*\}', '', text)
                    
                    subtitles.append(Subtitle(
                        index=len(subtitles) + 1,
                        start=start,
                        end=end,
                        text=text,
                        style=sub_dict.get('style', 'Default'),
                        name=sub_dict.get('name', ''),
                        margin_l=int(sub_dict.get('marginl', 0) or 0),
                        margin_r=int(sub_dict.get('marginr', 0) or 0),
                        margin_v=int(sub_dict.get('marginv', 0) or 0),
                        effect=sub_dict.get('effect', '')
                    ))
    
    return subtitles, metadata


def write_ass(subtitles: List[Subtitle], output_path: str, 
              metadata: Optional[ASSMetadata] = None) -> None:
    """
    写出 ASS 字幕文件
    
    Args:
        subtitles: 字幕列表
        output_path: 输出文件路径
        metadata: ASS 元数据（可选，如果不提供则使用默认模板）
    """
    if metadata is None:
        metadata = _default_ass_metadata()
    
    with open(output_path, 'w', encoding='utf-8') as f:
        # 写入 Script Info
        for line in metadata.script_info:
            f.write(f"{line}\n")
        f.write("\n")
        
        # 写入 Styles
        for line in metadata.styles:
            f.write(f"{line}\n")
        f.write("\n")
        
        # 写入 Events
        f.write("[Events]\n")
        f.write(metadata.events_header + "\n")
        
        for sub in subtitles:
            start = _srt_time_to_ass(sub.start)
            end = _srt_time_to_ass(sub.end)
            text = sub.text.replace('\n', '\\N')
            
            f.write(f"Dialogue: 0,{start},{end},{sub.style},{sub.name},"
                   f"{sub.margin_l},{sub.margin_r},{sub.margin_v},{sub.effect},{text}\n")


def _ass_time_to_srt(ass_time: str) -> str:
    """将 ASS 时间格式转换为 SRT 时间格式
    
    ASS: h:mm:ss.cc (centiseconds)
    SRT: hh:mm:ss,mmm (milliseconds)
    """
    match = re.match(r'(\d+):(\d{2}):(\d{2})\.(\d{2})', ass_time)
    if match:
        h, m, s, cs = match.groups()
        ms = int(cs) * 10
        return f"{int(h):02d}:{m}:{s},{ms:03d}"
    return "00:00:00,000"


def _srt_time_to_ass(srt_time: str) -> str:
    """将 SRT 时间格式转换为 ASS 时间格式
    
    SRT: hh:mm:ss,mmm (milliseconds)
    ASS: h:mm:ss.cc (centiseconds)
    """
    match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', srt_time)
    if match:
        h, m, s, ms = match.groups()
        cs = int(ms) // 10
        return f"{int(h)}:{m}:{s}.{cs:02d}"
    return "0:00:00.00"


def _default_ass_metadata() -> ASSMetadata:
    """返回默认的 ASS 元数据"""
    return ASSMetadata(
        script_info=[
            "[Script Info]",
            "ScriptType: v4.00+",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "WrapStyle: 0"
        ],
        styles=[
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1"
        ],
        events_header="Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    )


def detect_subtitle_format(file_path: str) -> str:
    """
    检测字幕文件格式
    
    Args:
        file_path: 文件路径
        
    Returns:
        'srt', 'ass', 'vtt' 或 'unknown'
    """
    ext = Path(file_path).suffix.lower()
    if ext == '.srt':
        return 'srt'
    elif ext in ['.ass', '.ssa']:
        return 'ass'
    elif ext == '.vtt':
        return 'vtt'
    return 'unknown'


def parse_subtitle(file_path: str) -> tuple[List[Subtitle], Optional[ASSMetadata]]:
    """
    自动检测格式并解析字幕文件
    
    Args:
        file_path: 字幕文件路径
        
    Returns:
        (字幕列表, ASS 元数据或 None)
    """
    fmt = detect_subtitle_format(file_path)
    
    if fmt == 'srt':
        return parse_srt(file_path), None
    elif fmt == 'ass':
        return parse_ass(file_path)
    elif fmt == 'vtt':
        return parse_vtt(file_path), None
    else:
        raise ValueError(f"不支持的字幕格式: {file_path}")


def write_subtitle(subtitles: List[Subtitle], output_path: str,
                   metadata: Optional[ASSMetadata] = None) -> None:
    """
    根据输出路径扩展名自动选择格式并写出字幕
    
    Args:
        subtitles: 字幕列表
        output_path: 输出文件路径
        metadata: ASS 元数据（仅用于 ASS 格式输出）
    """
    fmt = detect_subtitle_format(output_path)
    
    if fmt == 'srt':
        write_srt(subtitles, output_path)
    elif fmt == 'ass':
        write_ass(subtitles, output_path, metadata)
    elif fmt == 'vtt':
        write_vtt(subtitles, output_path)
    else:
        # 默认写为 SRT
        write_srt(subtitles, output_path)


if __name__ == '__main__':
    # 测试代码
    import sys
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        subs, meta = parse_subtitle(file_path)
        print(f"解析了 {len(subs)} 条字幕")
        for sub in subs[:3]:
            print(f"  [{sub.start} -> {sub.end}] {sub.text[:50]}...")
