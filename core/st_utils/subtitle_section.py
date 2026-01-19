"""
Streamlit 字幕翻译界面组件
"""

import streamlit as st
import os
from translations.translations import translate as t
from core.utils import load_key


# 支持的语言列表
LANGUAGES = {
    "🇺🇸 English": "en",
    "🇨🇳 简体中文": "zh", 
    "🇹🇼 繁體中文": "zh-TW",
    "🇪🇸 Español": "es",
    "🇷🇺 Русский": "ru",
    "🇫🇷 Français": "fr",
    "🇩🇪 Deutsch": "de",
    "🇮🇹 Italiano": "it",
    "🇯🇵 日本語": "ja",
    "🇰🇷 한국어": "ko",
    "🇵🇹 Português": "pt",
    "🇳🇱 Nederlands": "nl",
    "🇵🇱 Polski": "pl",
    "🇹🇷 Türkçe": "tr",
    "🇻🇳 Tiếng Việt": "vi",
    "🇹🇭 ไทย": "th",
    "🇮🇩 Bahasa Indonesia": "id",
    "🇸🇦 العربية": "ar",
}


def subtitle_translation_section():
    """字幕翻译界面 section"""
    st.header(t("📝 Subtitle Translation"))
    
    with st.container(border=True):
        st.markdown(f"""
        <p style='font-size: 18px;'>
        {t("Upload a subtitle file (SRT/ASS/VTT) and translate it to your target language.")}
        </p>
        """, unsafe_allow_html=True)
        
        # 文件上传
        uploaded_file = st.file_uploader(
            t("Upload Subtitle File"),
            type=['srt', 'ass', 'ssa', 'vtt'],
            help=t("Supported formats: SRT, ASS, SSA, VTT")
        )
        
        # 语言选择
        col1, col2 = st.columns(2)
        
        with col1:
            source_lang = st.selectbox(
                t("Source Language"),
                options=list(LANGUAGES.keys()),
                index=0,
                help=t("Select the language of the original subtitle")
            )
        
        with col2:
            # 默认选择配置中的目标语言
            default_target = load_key("target_language") or "简体中文"
            target_options = list(LANGUAGES.keys())
            
            # 尝试找到匹配的默认值
            default_index = 1  # 默认简体中文
            for i, (name, code) in enumerate(LANGUAGES.items()):
                if code in default_target or default_target in name:
                    default_index = i
                    break
            
            target_lang = st.selectbox(
                t("Target Language"),
                options=target_options,
                index=default_index,
                help=t("Select the language to translate to")
            )
        
        # 高级选项
        with st.expander(t("Advanced Options")):
            chunk_size = st.slider(
                t("Chunk Size"),
                min_value=5,
                max_value=20,
                value=10,
                help=t("Number of subtitle lines to translate at once")
            )
            
            theme_prompt = st.text_area(
                t("Theme Description (Optional)"),
                placeholder=t("Describe the video content to improve translation quality..."),
                help=t("Provide context about the video to help translation")
            )
        
        # 翻译按钮
        if uploaded_file is not None:
            if st.button(t("🚀 Start Translating"), key="translate_subtitle_button"):
                translate_uploaded_subtitle(
                    uploaded_file,
                    LANGUAGES[source_lang],
                    LANGUAGES[target_lang],
                    chunk_size,
                    theme_prompt if theme_prompt else None
                )


def translate_uploaded_subtitle(uploaded_file, source_lang: str, target_lang: str,
                                 chunk_size: int, theme_prompt: str = None):
    """翻译上传的字幕文件"""
    from core.translate_subtitle import translate_subtitle_file
    
    # 确保 output 目录存在
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    # 获取文件名和扩展名
    original_name = uploaded_file.name
    base_name, suffix = os.path.splitext(original_name)
    
    # 保存上传的文件到 output 目录
    input_path = os.path.join(output_dir, original_name)
    with open(input_path, 'wb') as f:
        f.write(uploaded_file.getvalue())
    
    # 输出文件路径
    output_filename = f"{base_name}_translated{suffix}"
    output_path = os.path.join(output_dir, output_filename)
    
    try:
        with st.spinner(t("Translating subtitle file...")):
            output_files = translate_subtitle_file(
                input_path=input_path,
                output_path=output_path,
                source_language=source_lang,
                target_language=target_lang,
                theme_prompt=theme_prompt,
                chunk_size=chunk_size,
                output_bilingual=True
            )
        
        st.success(t("✅ Translation complete!"))
        st.info(f"{t('Output saved to')}: `{output_dir}/`")
        
        # 显示所有输出文件并提供下载按钮
        st.subheader(t("📁 Generated Files"))
        
        file_labels = {
            'translation': ('📝 ' + t('Translation Only'), f'{base_name}_translated{suffix}'),
            'source': ('📄 ' + t('Source Only'), f'{base_name}_src{suffix}'),
            'bilingual': ('🔤 ' + t('Bilingual (Source on top)'), f'{base_name}_bilingual{suffix}'),
            'bilingual_reverse': ('🔤 ' + t('Bilingual (Translation on top)'), f'{base_name}_bilingual_reverse{suffix}')
        }
        
        cols = st.columns(2)
        for idx, (key, (label, filename)) in enumerate(file_labels.items()):
            if key in output_files:
                with cols[idx % 2]:
                    file_path = output_files[key]
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    st.download_button(
                        label=label,
                        data=content,
                        file_name=filename,
                        mime="text/plain",
                        key=f"download_{key}"
                    )
        
    except Exception as e:
        st.error(f"{t('Translation failed')}: {str(e)}")
        import traceback
        st.code(traceback.format_exc())


if __name__ == '__main__':
    # 用于测试
    subtitle_translation_section()

