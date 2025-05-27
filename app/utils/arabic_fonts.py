# إعداد الخطوط العربية لتقارير PDF
# ضع هذا الملف في app/utils/arabic_fonts.py

import os
import requests
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping

def download_arabic_font():
    """تحميل خط عربي تلقائياً من الإنترنت"""
    fonts_dir = Path(__file__).parent.parent / 'fonts'
    fonts_dir.mkdir(exist_ok=True)
    
    font_path = fonts_dir / 'NotoSansArabic-Regular.ttf'
    
    if not font_path.exists():
        print("تحميل الخط العربي...")
        try:
            # رابط تحميل خط Noto Sans Arabic
            font_url = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansArabic/NotoSansArabic-Regular.ttf"
            
            response = requests.get(font_url, timeout=30)
            response.raise_for_status()
            
            with open(font_path, 'wb') as f:
                f.write(response.content)
            
            print(f"تم تحميل الخط بنجاح: {font_path}")
            return str(font_path)
            
        except Exception as e:
            print(f"فشل في تحميل الخط: {e}")
            return None
    else:
        print(f"الخط موجود: {font_path}")
        return str(font_path)

def setup_arabic_fonts():
    """إعداد الخطوط العربية"""
    
    # 1. محاولة تحميل خط عربي
    font_path = download_arabic_font()
    
    if font_path and os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont('Arabic', font_path))
            pdfmetrics.registerFont(TTFont('Arabic-Bold', font_path))
            addMapping('Arabic', 0, 0, 'Arabic')
            addMapping('Arabic', 1, 0, 'Arabic-Bold')
            print("تم تسجيل الخط العربي بنجاح")
            return True
        except Exception as e:
            print(f"فشل في تسجيل الخط العربي: {e}")
    
    # 2. محاولة استخدام خطوط النظام
    system_fonts = [
        # Linux
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/TTF/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        
        # Windows
        'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/tahoma.ttf',
        
        # macOS
        '/System/Library/Fonts/Arial.ttf',
        '/Library/Fonts/Arial.ttf',
    ]
    
    for font_path in system_fonts:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('Arabic', font_path))
                addMapping('Arabic', 0, 0, 'Arabic')
                print(f"تم تسجيل خط النظام: {font_path}")
                return True
            except Exception as e:
                continue
    
    print("تحذير: لم يتم العثور على خط عربي مناسب")
    return False

# معلومات إضافية حول الخطوط العربية
ARABIC_FONTS_INFO = {
    'recommended_fonts': [
        {
            'name': 'Noto Sans Arabic',
            'url': 'https://fonts.google.com/noto/specimen/Noto+Sans+Arabic',
            'description': 'خط مفتوح المصدر من Google، يدعم العربية بشكل ممتاز'
        },
        {
            'name': 'Cairo',
            'url': 'https://fonts.google.com/specimen/Cairo',
            'description': 'خط عربي حديث وأنيق'
        },
        {
            'name': 'Amiri',
            'url': 'https://fonts.google.com/specimen/Amiri',
            'description': 'خط تقليدي للنصوص العربية'
        }
    ],
    'system_fonts': {
        'windows': ['Tahoma', 'Arial Unicode MS', 'Segoe UI'],
        'macos': ['Geeza Pro', 'Baghdad', 'Nadeem'],
        'linux': ['DejaVu Sans', 'Liberation Sans', 'Ubuntu']
    }
}

def test_arabic_rendering():
    """اختبار عرض النصوص العربية"""
    from reportlab.platypus import SimpleDocTemplate, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import letter
    import io
    
    # إعداد الخطوط
    setup_arabic_fonts()
    
    # إنشاء مستند تجريبي
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    
    styles = getSampleStyleSheet()
    
    # اختبار النص العربي
    arabic_text = "مرحباً بكم في نظام إدارة الموارد البشرية"
    
    try:
        # محاولة استخدام الخط العربي
        from reportlab.lib.styles import ParagraphStyle
        arabic_style = ParagraphStyle(
            'Arabic',
            parent=styles['Normal'],
            fontName='Arabic',
            fontSize=14,
            alignment=2  # Right alignment
        )
        
        story = [Paragraph(arabic_text, arabic_style)]
        doc.build(story)
        
        print("✓ تم اختبار عرض النصوص العربية بنجاح")
        return True
        
    except Exception as e:
        print(f"✗ فشل في اختبار النصوص العربية: {e}")
        return False

if __name__ == "__main__":
    # تشغيل الاختبار
    print("بدء إعداد الخطوط العربية...")
    
    # إعداد الخطوط
    font_success = setup_arabic_fonts()
    
    if font_success:
        # اختبار العرض
        test_success = test_arabic_rendering()
        
        if test_success:
            print("\n✓ تم إعداد الخطوط العربية بنجاح!")
            print("يمكنك الآن استخدام تقارير PDF باللغة العربية")
        else:
            print("\n⚠ تم إعداد الخطوط ولكن فشل الاختبار")
    else:
        print("\n✗ فشل في إعداد الخطوط العربية")
        print("يرجى تحميل خط عربي يدوياً ووضعه في مجلد app/fonts/")
    
    # عرض معلومات الخطوط المُنصح بها
    print(f"\nالخطوط المُنصح بها:")
    for font in ARABIC_FONTS_INFO['recommended_fonts']:
        print(f"- {font['name']}: {font['description']}")
        print(f"  الرابط: {font['url']}")