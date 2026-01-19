"""
字幕翻译核心模块 - 复用 VideoLingo 现有翻译逻辑实现字幕文件翻译

主要功能:
    - translate_subtitle_file(): 翻译字幕文件主函数
    - translate_subtitle_chunks(): 分块并行翻译
"""

import concurrent.futures
from typing import List, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from core.subtitle_parser import Subtitle, parse_subtitle, write_subtitle
from core.translate_lines import translate_lines
from core.utils import load_key, update_key

console = Console()


def prepare_translation_config(source_language: str, target_language: str) -> None:
    """
    准备翻译所需的配置
    
    Args:
        source_language: 源语言
        target_language: 目标语言
    """
    # 临时设置源语言和目标语言
    update_key("whisper.detected_language", source_language)
    update_key("target_language", target_language)


def split_subtitles_into_chunks(subtitles: List[Subtitle], 
                                 chunk_size: int = 10) -> List[List[Subtitle]]:
    """
    将字幕列表分割成多个块
    
    Args:
        subtitles: 字幕列表
        chunk_size: 每块的字幕数量
        
    Returns:
        字幕块列表
    """
    chunks = []
    for i in range(0, len(subtitles), chunk_size):
        chunks.append(subtitles[i:i + chunk_size])
    return chunks


def translate_chunk(chunk: List[Subtitle], 
                    chunks: List[List[Subtitle]], 
                    chunk_index: int,
                    theme_prompt: Optional[str] = None) -> tuple[int, List[str]]:
    """
    翻译单个字幕块
    
    Args:
        chunk: 当前字幕块
        chunks: 所有字幕块
        chunk_index: 当前块索引
        theme_prompt: 主题提示（可选）
        
    Returns:
        (块索引, 翻译结果列表)
    """
    # 提取文本
    lines = '\n'.join([sub.text.replace('\n', ' ') for sub in chunk])
    
    # 获取上下文
    previous_content = None
    after_content = None
    
    if chunk_index > 0:
        prev_chunk = chunks[chunk_index - 1]
        previous_content = [sub.text for sub in prev_chunk[-3:]]
    
    if chunk_index < len(chunks) - 1:
        next_chunk = chunks[chunk_index + 1]
        after_content = [sub.text for sub in next_chunk[:2]]
    
    # 调用翻译
    translation, _ = translate_lines(
        lines, 
        previous_content, 
        after_content,
        things_to_note_prompt=None,
        summary_prompt=theme_prompt,
        index=chunk_index
    )
    
    # 分割翻译结果
    translated_lines = translation.split('\n')
    
    return chunk_index, translated_lines


def translate_subtitles(subtitles: List[Subtitle],
                        source_language: str,
                        target_language: str,
                        theme_prompt: Optional[str] = None,
                        chunk_size: int = 10,
                        max_workers: Optional[int] = None) -> List[Subtitle]:
    """
    翻译字幕列表
    
    Args:
        subtitles: 原始字幕列表
        source_language: 源语言
        target_language: 目标语言
        theme_prompt: 主题提示（可选）
        chunk_size: 每块字幕数量
        max_workers: 并行工作线程数
        
    Returns:
        翻译后的字幕列表
    """
    # 准备配置
    prepare_translation_config(source_language, target_language)
    
    if max_workers is None:
        max_workers = load_key("max_workers") or 3
    
    # 分块
    chunks = split_subtitles_into_chunks(subtitles, chunk_size)
    console.print(f"[cyan]将 {len(subtitles)} 条字幕分成 {len(chunks)} 个块进行翻译...[/cyan]")
    
    # 并行翻译
    results = []
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task("[cyan]翻译字幕中...", total=len(chunks))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for i, chunk in enumerate(chunks):
                future = executor.submit(translate_chunk, chunk, chunks, i, theme_prompt)
                futures.append(future)
            
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
                progress.update(task, advance=1)
    
    # 按顺序排列结果
    results.sort(key=lambda x: x[0])
    
    # 创建翻译后的字幕列表
    translated_subtitles = []
    for chunk_index, translated_lines in results:
        chunk = chunks[chunk_index]
        
        for i, sub in enumerate(chunk):
            # 处理翻译行数不匹配的情况
            if i < len(translated_lines):
                translated_text = translated_lines[i].strip()
            else:
                translated_text = sub.text  # 如果没有翻译，保留原文
                console.print(f"[yellow]警告: 第 {sub.index} 条字幕翻译缺失，保留原文[/yellow]")
            
            translated_subtitles.append(Subtitle(
                index=sub.index,
                start=sub.start,
                end=sub.end,
                text=translated_text,
                style=sub.style,
                name=sub.name,
                margin_l=sub.margin_l,
                margin_r=sub.margin_r,
                margin_v=sub.margin_v,
                effect=sub.effect
            ))
    
    return translated_subtitles


def translate_subtitle_file(input_path: str,
                            output_path: str,
                            source_language: str,
                            target_language: str,
                            theme_prompt: Optional[str] = None,
                            chunk_size: int = 10,
                            output_bilingual: bool = True) -> dict:
    """
    翻译字幕文件
    
    Args:
        input_path: 输入字幕文件路径
        output_path: 输出字幕文件路径（译文）
        source_language: 源语言
        target_language: 目标语言
        theme_prompt: 主题提示（可选）
        chunk_size: 每块字幕数量
        output_bilingual: 是否输出双语字幕
        
    Returns:
        包含所有输出文件路径的字典
    """
    import os
    
    console.print(f"[bold green]开始翻译字幕文件: {input_path}[/bold green]")
    console.print(f"[cyan]源语言: {source_language} -> 目标语言: {target_language}[/cyan]")
    
    # 解析输入文件
    subtitles, metadata = parse_subtitle(input_path)
    console.print(f"[cyan]解析了 {len(subtitles)} 条字幕[/cyan]")
    
    # 翻译
    translated_subtitles = translate_subtitles(
        subtitles,
        source_language,
        target_language,
        theme_prompt,
        chunk_size
    )
    
    # 准备输出路径
    base_path, ext = os.path.splitext(output_path)
    output_dir = os.path.dirname(output_path) or "."
    base_name = os.path.basename(base_path).replace("_translated", "")
    
    output_files = {}
    
    # 1. 输出译文字幕
    write_subtitle(translated_subtitles, output_path, metadata)
    output_files['translation'] = output_path
    console.print(f"[green]✅ 译文字幕: {output_path}[/green]")
    
    if output_bilingual:
        # 2. 输出原文字幕
        src_path = os.path.join(output_dir, f"{base_name}_src{ext}")
        write_subtitle(subtitles, src_path, metadata)
        output_files['source'] = src_path
        console.print(f"[green]✅ 原文字幕: {src_path}[/green]")
        
        # 3. 输出双语字幕 (原文在上，译文在下)
        bilingual_subtitles = []
        for orig, trans in zip(subtitles, translated_subtitles):
            bilingual_subtitles.append(Subtitle(
                index=orig.index,
                start=orig.start,
                end=orig.end,
                text=f"{orig.text}\n{trans.text}",
                style=orig.style,
                name=orig.name,
                margin_l=orig.margin_l,
                margin_r=orig.margin_r,
                margin_v=orig.margin_v,
                effect=orig.effect
            ))
        
        bilingual_path = os.path.join(output_dir, f"{base_name}_bilingual{ext}")
        write_subtitle(bilingual_subtitles, bilingual_path, metadata)
        output_files['bilingual'] = bilingual_path
        console.print(f"[green]✅ 双语字幕: {bilingual_path}[/green]")
        
        # 4. 输出双语字幕 (译文在上，原文在下)
        bilingual_reverse_subtitles = []
        for orig, trans in zip(subtitles, translated_subtitles):
            bilingual_reverse_subtitles.append(Subtitle(
                index=orig.index,
                start=orig.start,
                end=orig.end,
                text=f"{trans.text}\n{orig.text}",
                style=orig.style,
                name=orig.name,
                margin_l=orig.margin_l,
                margin_r=orig.margin_r,
                margin_v=orig.margin_v,
                effect=orig.effect
            ))
        
        bilingual_reverse_path = os.path.join(output_dir, f"{base_name}_bilingual_reverse{ext}")
        write_subtitle(bilingual_reverse_subtitles, bilingual_reverse_path, metadata)
        output_files['bilingual_reverse'] = bilingual_reverse_path
        console.print(f"[green]✅ 双语字幕(译文优先): {bilingual_reverse_path}[/green]")
    
    console.print(f"[bold green]✅ 翻译完成! 共生成 {len(output_files)} 个字幕文件[/bold green]")
    
    return output_files


if __name__ == '__main__':
    # 测试代码
    import sys
    if len(sys.argv) >= 4:
        input_file = sys.argv[1]
        source = sys.argv[2]
        target = sys.argv[3]
        output = sys.argv[4] if len(sys.argv) > 4 else input_file.replace('.srt', '_translated.srt')
        
        translate_subtitle_file(input_file, output, source, target)
    else:
        print("用法: python translate_subtitle.py <input.srt> <source_lang> <target_lang> [output.srt]")

