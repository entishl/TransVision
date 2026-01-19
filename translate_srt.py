#!/usr/bin/env python
"""
字幕翻译命令行工具

用法:
    python translate_srt.py input.srt --source en --target 简体中文 [--output output.srt]
    
示例:
    python translate_srt.py video.srt -s en -t 简体中文
    python translate_srt.py video.ass -s ja -t 简体中文 -o video_cn.ass
"""

import argparse
import os
import sys

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from core.translate_subtitle import translate_subtitle_file
from core.subtitle_parser import detect_subtitle_format
from core.utils import load_key
from rich.console import Console

console = Console()


def get_default_output_path(input_path: str) -> str:
    """生成默认输出路径"""
    base, ext = os.path.splitext(input_path)
    return f"{base}_translated{ext}"


def main():
    parser = argparse.ArgumentParser(
        description='VideoLingo 字幕翻译工具 - 独立翻译字幕文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python translate_srt.py video.srt -s en -t 简体中文
  python translate_srt.py video.ass -s ja -t 简体中文 -o video_cn.ass
  python translate_srt.py movie.srt --source English --target 日本語

支持的语言格式:
  可以使用 ISO 639-1 代码（如 en, zh, ja）或自然语言描述（如 English, 简体中文, 日本語）
        '''
    )
    
    parser.add_argument('input', 
                        help='输入字幕文件路径 (支持 .srt, .ass, .ssa)')
    
    parser.add_argument('-s', '--source', 
                        required=True,
                        help='源语言 (如: en, English, 英语)')
    
    parser.add_argument('-t', '--target',
                        default=None,
                        help='目标语言 (如: zh, 简体中文)，默认使用 config.yaml 中的设置')
    
    parser.add_argument('-o', '--output',
                        default=None,
                        help='输出文件路径，默认为 <input>_translated.<ext>')
    
    parser.add_argument('--chunk-size',
                        type=int,
                        default=10,
                        help='每次翻译的字幕行数 (默认: 10)')
    
    parser.add_argument('--theme',
                        default=None,
                        help='视频主题描述（可选，帮助提升翻译质量）')

    args = parser.parse_args()
    
    # 检查输入文件
    if not os.path.exists(args.input):
        console.print(f"[red]错误: 文件不存在: {args.input}[/red]")
        sys.exit(1)
    
    # 检查文件格式
    fmt = detect_subtitle_format(args.input)
    if fmt == 'unknown':
        console.print(f"[red]错误: 不支持的字幕格式。支持的格式: .srt, .ass, .ssa[/red]")
        sys.exit(1)
    
    # 设置输出路径
    output_path = args.output or get_default_output_path(args.input)
    
    # 设置目标语言
    target_language = args.target or load_key("target_language")
    if not target_language:
        console.print("[red]错误: 未指定目标语言，请使用 -t 参数或在 config.yaml 中设置 target_language[/red]")
        sys.exit(1)
    
    # 开始翻译
    try:
        translate_subtitle_file(
            input_path=args.input,
            output_path=output_path,
            source_language=args.source,
            target_language=target_language,
            theme_prompt=args.theme,
            chunk_size=args.chunk_size
        )
    except Exception as e:
        console.print(f"[red]翻译失败: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
