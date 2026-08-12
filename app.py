import streamlit as st
import pdfplumber
import re
import pandas as pd
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="لوحة تحكم تقارير الهلال الأحمر", layout="wide")

st.title(" نظام تحليل تقارير الهلال الأحمر - مستشفي المواساة بالخبر ")
st.write("قم برفع ملفات تقارير الهلال الأحمر (PDF) لتحليلها واستعراض الخريطة والإحصائيات التراكمية.")

# دالة استخراج البيانات من ملفات PDF
def parse_epcr_pdf(pdf_file):
    data = {}
    with pdfplumber.open(pdf_file) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text() or ""
        
        # استخراج الإحداثيات
        coords_pattern = r"Ambulance started moving from ([\d\.\-]+),\s*([\d\.\-]+) to incident location ([\d\.\-]+),\s*([\d\.\-]+) then moved to hospital location ([\d\.\-]+),\s*([\d\.\-]+)"
        coords = re.search(coords_pattern, full_text)
        
        if coords:
            data['start_lat'], data['start_lon'] = float(coords.group(1)), float(coords.group(2))
            data['inc_lat'], data['inc_lon'] = float(coords.group(3)), float(coords.group(4))
            data['hosp_lat'], data['hosp_lon'] = float(coords.group(5)), float(coords.group(6))
        else:
            data['start_lat'] = data['start_lon'] = None
            data['inc_lat'] = data['inc_lon'] = None
            data['hosp_lat'] = data['hosp_lon'] = None

        # رقم البلاغ
        report_num = re.search(r"رقم البلاغ\s*(\d+)", full_text)
        data['رقم البلاغ'] = report_num.group(1) if report_num else "غير محدد"

        # التاريخ
        date_match = re.search(r"(\d{2}/\d{2}/\d{4})", full_text)
        data['التاريخ'] = date_match.group(1) if date_match else "غير محدد"

        # الحي والمدينة
        district = re.search(r"الحي:\s*([^\n]+)", full_text)
        data['الحي'] = district.group(1).strip() if district else "غير محدد"
        
        city = re.search(r"المدينة:\s*([^\n]+)", full_text)
        data['المدينة'] = city.group(1).strip() if city else "غير محدد"

        # اسم المسعف والمركز
        paramedic = re.search(r"المسعف الأول\s*\n\s*([^\n]+)", full_text)
        data['المسعف الأول'] = paramedic.group(1).strip() if paramedic else "غير محدد"

        center = re.search(r"المركز:\s*([^\n]+)", full_text)
        data['المركز'] = center.group(1).strip() if center else "غير محدد"

    return data

# واجهة رفع الملفات
uploaded_files = st.file_uploader("اختر ملفات الـ PDF الخاصة بالهلال الأحمر", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    reports_data = []
    for file in uploaded_files:
        try:
            parsed = parse_epcr_pdf(file)
            reports_data.append(parsed)
        except Exception as e:
            st.error(f"خطأ في قراءة الملف {file.name}")

    df = pd.DataFrame(reports_data)

    # إحصائيات سريعة
    st.subheader("📊 إحصائيات عامة")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("إجمالي الحالات", len(df))
    c2.metric("أكثر المدن بلاغاً", df['المدينة'].mode()[0] if not df['المدينة'].empty else "N/A")
    c3.metric("أكثر الأحياء طلبًا", df['الحي'].mode()[0] if not df['الحي'].empty else "N/A")
    c4.metric("المراكز النشطة", df['المركز'].nunique())

    st.markdown("---")

    # الخريطة
    st.subheader("🗺️ خريطة المواقع")
    map_df = df.dropna(subset=['inc_lat', 'inc_lon'])
    
    if not map_df.empty:
        m = folium.Map(location=[map_df.iloc[0]['inc_lat'], map_df.iloc[0]['inc_lon']], zoom_start=12)
        for _, row in map_df.iterrows():
            folium.Marker([row['start_lat'], row['start_lon']], popup=f"مركز: {row['المركز']}", icon=folium.Icon(color="blue")).add_to(m)
            folium.Marker([row['inc_lat'], row['inc_lon']], popup=f"بلاغ: {row['رقم البلاغ']}", icon=folium.Icon(color="red")).add_to(m)
            folium.Marker([row['hosp_lat'], row['hosp_lon']], popup="مستشفى المواساة", icon=folium.Icon(color="green")).add_to(m)
            folium.PolyLine([[row['start_lat'], row['start_lon']], [row['inc_lat'], row['inc_lon']], [row['hosp_lat'], row['hosp_lon']]], color="red").add_to(m)
        st_folium(m, width=1200, height=500)

    st.markdown("---")

    # الجدول وتحميل الأكسيل
    st.subheader("📋 البيانات التفصيلية")
    st.dataframe(df)
    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 تحميل البيانات أكسيل (CSV)", csv, "reports_summary.csv", "text/csv")
