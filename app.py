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

# --- قسم ضبط المفتاح ---
api_key = st.sidebar.text_input("إدخال Gemini API Key (للاستخراج الذكي):", type="password")

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
    1. ابحث عن الإحداثيات في آخر الصفحة بنفس الصيغة: Ambulance started moving from LAT, LON to incident location LAT, LON then moved to hospital location LAT, LON وضارب الإحداثيات بالترتيب (start_lat, start_lon, inc_lat, inc_lon, hosp_lat, hosp_lon).
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
    # كود احتياطي يستخرج الإحداثيات بالنص العادي في حال عدم توفر المفتاح
    data = {}
    with pdfplumber.open(pdf_file) as pdf:
        full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        
        # استخراج الإحداثيات من السطر الإنجليزي الأخير
        coords_match = re.search(r"moving from ([\d\.]+),\s*([\d\.]+) to incident location ([\d\.]+),\s*([\d\.]+) then moved to hospital location ([\d\.]+),\s*([\d\.]+)", full_text)
        if coords_match:
            data['start_lat'], data['start_lon'] = float(coords_match.group(1)), float(coords_match.group(2))
            data['inc_lat'], data['inc_lon'] = float(coords_match.group(3)), float(coords_match.group(4))
            data['hosp_lat'], data['hosp_lon'] = float(coords_match.group(5)), float(coords_match.group(6))
        else:
            data['start_lat'] = data['start_lon'] = data['inc_lat'] = data['inc_lon'] = data['hosp_lat'] = data['hosp_lon'] = None

        # استخراج عينة بسيطة برمجياً
        data['اسم الملف'] = pdf_file.name
        data['ملاحظة'] = "تم الاستخراج بالنظام العادي (أدخل Gemini API Key لاستخراج باقي التفاصيل)"
    return data

# --- رفع الملفات ---
uploaded_files = st.file_uploader("رفع تقارير PDF", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    reports = []
    for f in uploaded_files:
        try:
            if api_key:
                parsed = extract_with_gemini(f, api_key)
            else:
                parsed = extract_fallback(f)
            parsed['اسم الملف'] = f.name
            reports.append(parsed)
        except Exception as e:
            st.error(f"حدث خطأ في تحليل الملف {f.name}: {e}")

    if reports:
        df = pd.DataFrame(reports)

        # --- رسم الخريطة مع المسار ---
        st.subheader("🗺️ خريطة مسار الإسعاف (المركز ⬅️ الحادث ⬅️ المستشفى)")
        
        # التحقق من وجود إحداثيات رسم الخريطة
        map_data = df.dropna(subset=['inc_lat', 'inc_lon'])
        if not map_data.empty:
            row = map_data.iloc[0]
            m = folium.Map(location=[row['inc_lat'], row['inc_lon']], zoom_start=12)
            
            points = []
            # 1. مركز الإسعاف
            if pd.notnull(row.get('start_lat')) and pd.notnull(row.get('start_lon')):
                start_pt = [row['start_lat'], row['start_lon']]
                folium.Marker(start_pt, popup="مركز الإسعاف", icon=folium.Icon(color="green", icon="home")).add_to(m)
                points.append(start_pt)

            # 2. موقع الحادث (المريض)
            inc_pt = [row['inc_lat'], row['inc_lon']]
            folium.Marker(inc_pt, popup=f"موقع الحادث - بلاغ {row.get('رقم البلاغ', '')}", icon=folium.Icon(color="red", icon="user")).add_to(m)
            points.append(inc_pt)

            # 3. المستشفى
            if pd.notnull(row.get('hosp_lat')) and pd.notnull(row.get('hosp_lon')):
                hosp_pt = [row['hosp_lat'], row['hosp_lon']]
                folium.Marker(hosp_pt, popup="المستشفى", icon=folium.Icon(color="blue", icon="plus")).add_to(m)
                points.append(hosp_pt)

            # رسم خط المسار إذا توفرت نقطتان أو أكثر
            if len(points) >= 2:
                folium.PolyLine(points, color="blue", weight=4, opacity=0.7).add_to(m)

            st_folium(m, width=1200, height=450)
        else:
            st.warning("لم يتم العثور على بيانات إحداثيات داخل الملف لرسم الخريطة.")

        st.markdown("---")
        st.subheader("📋 التفاصيل المستخرجة من التقارير")
        st.dataframe(df)

        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 تحميل البيانات (Excel/CSV)", csv, "epcr_parsed.csv", "text/csv")
