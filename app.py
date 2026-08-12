import streamlit as st
import pandas as pd
import json
import re
import pdfplumber
import folium
from streamlit_folium import st_folium
import google.generativeai as genai

st.set_page_config(page_title="تحليل تقارير الهلال الأحمر", layout="wide")

st.title("🚑 نظام تحليل تقارير الهلال الأحمر - مستشفى المواساة الخبر")
st.markdown("استخراج شامل لجميع بيانات تقارير (ePCR) والمسار الجغرافي.")

# --- المفتاح الخاص بك مثبت هنا تلقائياً ---
API_KEY = "AQ.Ab8RN6ILmelHYZiivZzo8lPE_9Zw_ETwJWhYDMekpjpb7Es2CA"

def extract_with_gemini(pdf_file, key):
    genai.configure(api_key=key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = """
    أنت خبير في تحليل تقارير الهلال الأحمر ePCR. استخرج البيانات التالية من التقرير بدقة متناهية.
    يجب أن تكون النتيجة عبارة عن JSON فقط بدون أي كلام آخر أو أسطر برمجية:
    {
      "رقم البلاغ": "الرقم",
      "التاريخ": "تاريخ البلاغ",
      "وقت البلاغ": "الوقت",
      "اسم المريض": "الاسم الكامل",
      "رقم الهوية": "رقم الهوية/الإقامة",
      "العمر": "العمر",
      "الجنس": "النوع",
      "المدينة": "اسم المدينة",
      "الحي": "اسم الحي",
      "الشكوى الرئيسية": "الشكوى",
      "التشخيص المبدئي": "التشخيص",
      "الموجه الطبي": "اسم الطبيب الموجه",
      "اسم المسعف الأول": "الاسم",
      "اسم المسعف الثاني": "الاسم",
      "start_lat": null,
      "start_lon": null,
      "inc_lat": null,
      "inc_lon": null,
      "hosp_lat": null,
      "hosp_lon": null
    }
    تنبيه للأماكن:
    1. ابحث عن الإحداثيات في آخر الصفحة بنفس الصيغة: Ambulance started moving from LAT, LON to incident location LAT, LON then moved to hospital location LAT, LON واستخرج الإحداثيات بالترتيب (start_lat, start_lon, inc_lat, inc_lon, hosp_lat, hosp_lon).
    2. أسماء المسعفين موجودة تحت جدول التوقيعات في آخر صفحة.
    """
    
    pdf_bytes = pdf_file.read()
    response = model.generate_content([
        {"mime_type": "application/pdf", "data": pdf_bytes},
        prompt
    ])
    
    # تنظيف وتنسيق المخرجات
    txt = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(txt)

def extract_fallback(pdf_file):
    data = {}
    with pdfplumber.open(pdf_file) as pdf:
        full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        coords_match = re.search(r"moving from ([\d\.]+),\s*([\d\.]+) to incident location ([\d\.]+),\s*([\d\.]+) then moved to hospital location ([\d\.]+),\s*([\d\.]+)", full_text)
        if coords_match:
            data['start_lat'], data['start_lon'] = float(coords_match.group(1)), float(coords_match.group(2))
            data['inc_lat'], data['inc_lon'] = float(coords_match.group(3)), float(coords_match.group(4))
            data['hosp_lat'], data['hosp_lon'] = float(coords_match.group(5)), float(coords_match.group(6))
        else:
            data['start_lat'] = data['start_lon'] = data['inc_lat'] = data['inc_lon'] = data['hosp_lat'] = data['hosp_lon'] = None
    return data

# --- رفع الملفات ---
uploaded_files = st.file_uploader("رفع تقارير PDF", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    reports = []
    for f in uploaded_files:
        try:
            # محاولة الاستخراج عبر الذكاء الاصطناعي بالمفتاح المثبت
            parsed = extract_with_gemini(f, API_KEY)
            parsed['اسم الملف'] = f.name
            reports.append(parsed)
        except Exception as e:
            # في حال وجود أي خطأ يتم الانتقال للنظام الاحتياطي
            parsed = extract_fallback(f)
            parsed['اسم الملف'] = f.name
            parsed['خطأ الاستخراج الذكي'] = str(e)
            reports.append(parsed)

    if reports:
        df = pd.DataFrame(reports)

        # --- رسم الخريطة مع المسار ---
        st.subheader("🗺️ خريطة مسار الإسعاف (المركز ⬅️ الحادث ⬅️ المستشفى)")
        
        map_data = df.dropna(subset=['inc_lat', 'inc_lon'])
        if not map_data.empty:
            row = map_data.iloc[0]
            m = folium.Map(location=[row['inc_lat'], row['inc_lon']], zoom_start=12)
            
            points = []
            if pd.notnull(row.get('start_lat')) and pd.notnull(row.get('start_lon')):
                start_pt = [float(row['start_lat']), float(row['start_lon'])]
                folium.Marker(start_pt, popup="مركز الإسعاف", icon=folium.Icon(color="green", icon="home")).add_to(m)
                points.append(start_pt)

            inc_pt = [float(row['inc_lat']), float(row['inc_lon'])]
            folium.Marker(inc_pt, popup=f"موقع الحادث - بلاغ {row.get('رقم البلاغ', '')}", icon=folium.Icon(color="red", icon="user")).add_to(m)
            points.append(inc_pt)

            if pd.notnull(row.get('hosp_lat')) and pd.notnull(row.get('hosp_lon')):
                hosp_pt = [float(row['hosp_lat']), float(row['hosp_lon'])]
                folium.Marker(hosp_pt, popup="المستشفى", icon=folium.Icon(color="blue", icon="plus")).add_to(m)
                points.append(hosp_pt)

            if len(points) >= 2:
                folium.PolyLine(points, color="blue", weight=4, opacity=0.7).add_to(m)

            st_folium(m, width=1200, height=450)
        else:
            st.warning("لم يتم العثور على إحداثيات داخل الملف لرسم الخريطة.")

        st.markdown("---")
        st.subheader("📋 التفاصيل المستخرجة من التقارير")
        st.dataframe(df)

        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 تحميل البيانات (Excel/CSV)", csv, "epcr_parsed.csv", "text/csv")
