import streamlit as st
import pandas as pd
import pdfplumber
import re
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="نظام تحليل تقارير الهلال الأحمر", layout="wide")

st.title("🚑 نظام تحليل تقارير الهلال الأحمر - مستشفى المواساة الخبر")
st.markdown("استخراج بيانات تقارير (ePCR) والمسار الجغرافي تلقائياً.")

def parse_epcr(pdf_file):
    data = {'اسم الملف': pdf_file.name}
    
    with pdfplumber.open(pdf_file) as pdf:
        full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        
        # استخراج رقم البلاغ
        report_num = re.search(r"رقم البلاغ\s*[:\-]?\s*(\d+)", full_text)
        data['رقم البلاغ'] = report_num.group(1) if report_num else "N/A"
        
        # استخراج اسم المريض
        patient_name = re.search(r"اسم المريض\s*[:\-]?\s*([^\n]+)", full_text)
        data['اسم المريض'] = patient_name.group(1).strip() if patient_name else "N/A"
        
        # استخراج العمر والجنس
        age = re.search(r"العمر\s*[:\-]?\s*(\d+)", full_text)
        data['العمر'] = age.group(1) if age else "N/A"
        
        # استخراج الإحداثيات من السطر الأخير باللغة الإنجليزية
        coords_pattern = r"moving from ([\d\.]+),\s*([\d\.]+) to incident location ([\d\.]+),\s*([\d\.]+) then moved to hospital location ([\d\.]+),\s*([\d\.]+)"
        coords_match = re.search(coords_pattern, full_text)
        
        if coords_match:
            data['start_lat'] = float(coords_match.group(1))
            data['start_lon'] = float(coords_match.group(2))
            data['inc_lat'] = float(coords_match.group(3))
            data['inc_lon'] = float(coords_match.group(4))
            data['hosp_lat'] = float(coords_match.group(5))
            data['hosp_lon'] = float(coords_match.group(6))
        else:
            data['start_lat'] = data['start_lon'] = data['inc_lat'] = data['inc_lon'] = data['hosp_lat'] = data['hosp_lon'] = None
            
    return data

# رفع الملفات
uploaded_files = st.file_uploader("رفع تقارير PDF", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    reports = [parse_epcr(f) for f in uploaded_files]
    df = pd.DataFrame(reports)

    # عرض الخريطة
    st.subheader("🗺️ خريطة مسار الإسعاف")
    map_data = df.dropna(subset=['inc_lat', 'inc_lon'])
    
    if not map_data.empty:
        row = map_data.iloc[0]
        m = folium.Map(location=[row['inc_lat'], row['inc_lon']], zoom_start=12)
        
        points = []
        if row['start_lat']:
            pts = [row['start_lat'], row['start_lon']]
            folium.Marker(pts, popup="مركز الإسعاف", icon=folium.Icon(color="green", icon="home")).add_to(m)
            points.append(pts)

        pts_inc = [row['inc_lat'], row['inc_lon']]
        folium.Marker(pts_inc, popup=f"موقع الحادث - بلاغ {row['رقم البلاغ']}", icon=folium.Icon(color="red", icon="user")).add_to(m)
        points.append(pts_inc)

        if row['hosp_lat']:
            pts_hosp = [row['hosp_lat'], row['hosp_lon']]
            folium.Marker(pts_hosp, popup="المستشفى", icon=folium.Icon(color="blue", icon="plus")).add_to(m)
            points.append(pts_hosp)

        if len(points) >= 2:
            folium.PolyLine(points, color="blue", weight=4).add_to(m)

        st_folium(m, width=1200, height=450)
    else:
        st.warning("لم يتم العثور على إحداثيات داخل الملف لرسم الخريطة.")

    st.markdown("---")
    st.subheader("📋 التفاصيل المستخرجة")
    st.dataframe(df)
