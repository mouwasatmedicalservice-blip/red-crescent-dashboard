import streamlit as st
import pdfplumber
import re
import pandas as pd
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="لوحة تحكم تقارير الهلال الأحمر - مستشفى المواساة", layout="wide")

st.title("🚑 نظام تحليل تقارير الهلال الأحمر - مستشفى المواساة الخبر")
st.markdown("يقوم هذا النظام بقراءة تقارير (ePCR) الشاملة واستخراج كافة البيانات والجداول تلقائياً.")

def parse_pdf_smart(pdf_file):
    data = {}
    
    with pdfplumber.open(pdf_file) as pdf:
        full_text = ""
        all_tables = []
        
        for page in pdf.pages:
            # استخراج النصوص
            txt = page.extract_text() or ""
            full_text += txt + "\n"
            
            # استخراج الجداول إن وجدت
            tables = page.extract_tables()
            for t in tables:
                all_tables.extend(t)

        # 1. البحث عن الإحداثيات (الأهم للخريطة)
        coords_pattern = r"([\d\.\-]+),\s*([\d\.\-]+)\s+to incident location\s+([\d\.\-]+),\s*([\d\.\-]+)\s+then moved to hospital location\s+([\d\.\-]+),\s*([\d\.\-]+)"
        coords = re.search(coords_pattern, full_text)
        if coords:
            data['start_lat'], data['start_lon'] = float(coords.group(1)), float(coords.group(2))
            data['inc_lat'], data['inc_lon'] = float(coords.group(3)), float(coords.group(4))
            data['hosp_lat'], data['hosp_lon'] = float(coords.group(5)), float(coords.group(6))
        else:
            # تجربة استخراج أي أرقام إحداثيات (خطوط الطول والعرض)
            any_coords = re.findall(r"(\d{2}\.\d+),\s*(\d{2}\.\d+)", full_text)
            if len(any_coords) >= 1:
                data['inc_lat'], data['inc_lon'] = float(any_coords[0][0]), float(any_coords[0][1])
                data['start_lat'] = data['start_lon'] = data['hosp_lat'] = data['hosp_lon'] = None
            else:
                data['start_lat'] = data['start_lon'] = data['inc_lat'] = data['inc_lon'] = data['hosp_lat'] = data['hosp_lon'] = None

        # دالة مساعدة للبحث المرن في النص
        def search_flexible(pattern, text, default="غير محدد"):
            match = re.search(pattern, text)
            return match.group(1).strip() if match else default

        # 2. استخراج الحقول الأساسية بأنماط مرنة جداً
        data['رقم البلاغ'] = search_flexible(r"(?:رقم البلاغ|Report No|Incident No)[:\s]*(\d+)", full_text)
        data['اسم المريض'] = search_flexible(r"(?:الأسم|اسم المريض|Patient Name)[:\s]*([^\n]+)", full_text)
        data['رقم الهوية/الإقامة'] = search_flexible(r"(?:رقم الهوية|الإقامة|National ID)[:\s]*(\d+)", full_text)
        data['العمر'] = search_flexible(r"(?:العمر|Age)[:\s]*([^\n]+)", full_text)
        data['الجنس'] = search_flexible(r"(?:النوع|الجنس|Gender)[:\s]*([^\n]+)", full_text)
        data['نوع البلاغ'] = search_flexible(r"(?:نوع البلاغ|Incident Type)[:\s]*([^\n]+)", full_text)
        data['المدينة'] = search_flexible(r"(?:المدينة|City)[:\s]*([^\n]+)", full_text)
        data['الحي'] = search_flexible(r"(?:الحي|District)[:\s]*([^\n]+)", full_text)
        data['المركز'] = search_flexible(r"(?:المركز|Station)[:\s]*([^\n]+)", full_text)
        data['الفرقة'] = search_flexible(r"(?:الفرقة|Unit)[:\s]*([^\n]+)", full_text)

        # 3. بيانات التأمين والتطبيب
        data['التشخيص المبدئي'] = search_flexible(r"(?:التشخيص المبدئي|Impression)[:\s]*([^\n]+)", full_text)
        data['شركة التأمين'] = search_flexible(r"(?:التأمين|Tawuniya|Insurance|الشركة)[:\s]*([^\n]+)", full_text)
        
        # 4. التواقيت
        data['وقت البلاغ'] = search_flexible(r"(?:وقت البلاغ|Call Time)[:\s]*([\d/\:\s]+)", full_text)
        data['وصول المستشفى'] = search_flexible(r"(?:وصول المستشفى|Hospital Arrival)[:\s]*([\d/\:\s]+)", full_text)

        # حفظ النص الكامل للمعاينة في حال الحاجة
        data['_raw_text_snippet'] = full_text[:300] if full_text else "نص فارغ"

    return data

# واجهة الشاشة
uploaded_files = st.file_uploader("رفع تقارير الـ PDF", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    reports = []
    for f in uploaded_files:
        parsed = parse_pdf_smart(f)
        parsed['اسم الملف'] = f.name
        reports.append(parsed)

    df = pd.DataFrame(reports)

    st.subheader("📊 ملخص التقرير")
    col1, col2, col3 = st.columns(3)
    col1.metric("عدد التقارير المرفوعة", len(df))
    col2.metric("الحالات التي تحتوي إحداثيات", len(df.dropna(subset=['inc_lat'])))
    col3.metric("اسم الملف الأول", df['اسم الملف'].iloc[0])

    st.markdown("---")

    # الخريطة
    st.subheader("🗺️ خريطة الموقع")
    map_df = df.dropna(subset=['inc_lat', 'inc_lon'])
    if not map_df.empty:
        m = folium.Map(location=[map_df.iloc[0]['inc_lat'], map_df.iloc[0]['inc_lon']], zoom_start=12)
        for _, r in map_df.iterrows():
            folium.Marker([r['inc_lat'], r['inc_lon']], popup=f"بلاغ: {r['رقم البلاغ']}", icon=folium.Icon(color="red")).add_to(m)
        st_folium(m, width=1200, height=450)
    else:
        st.warning("لم يتم العثور على إحداثيات موقع جغرافية داخل هذا التقرير لرسمها على الخريطة.")

    st.markdown("---")

    # عرض البيانات المستخرجة
    st.subheader("📋 البيانات المطلوبة")
    st.dataframe(df.drop(columns=['_raw_text_snippet'], errors='ignore'))

    # خيار التتبع التشخيصي (في حال استمرار قراءة N/A)
    with st.expander("🔍 أداة فحص النص المستخرج من التقرير (Debug)"):
        st.write("هذا هو الجزء الأول من النص الذي تمكن النظام من قراءته داخل ملفك:")
        st.code(df['_raw_text_snippet'].iloc[0] if not df.empty else "لا يوجد نص")

    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 تحميل البيانات Excel", csv, "report_data.csv", "text/csv")
