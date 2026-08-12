import streamlit as st
import pdfplumber
import re
import pandas as pd
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="لوحة تحكم تقارير الهلال الأحمر - مستشفى المواساة", layout="wide")

st.title("🚑 نظام تحليل تقارير الهلال الأحمر - مستشفى المواساة الخبر")
st.markdown("يقوم هذا النظام بقراءة تقارير (ePCR) بالكامل واستخراج بيانات الحوادث، التواقيت، العلامات الحيوية، والطاقم الطبي.")

def parse_full_epcr(pdf_file):
    data = {}
    with pdfplumber.open(pdf_file) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text() or ""
        
        # 1. الإحداثيات والمواقع من السطر الأخير
        coords_pattern = r"Ambulance started moving from ([\d\.\-]+),\s*([\d\.\-]+) to incident location ([\d\.\-]+),\s*([\d\.\-]+) then moved to hospital location ([\d\.\-]+),\s*([\d\.\-]+)"
        coords = re.search(coords_pattern, full_text)
        if coords:
            data['start_lat'], data['start_lon'] = float(coords.group(1)), float(coords.group(2))
            data['inc_lat'], data['inc_lon'] = float(coords.group(3)), float(coords.group(4))
            data['hosp_lat'], data['hosp_lon'] = float(coords.group(5)), float(coords.group(6))
        else:
            data['start_lat'] = data['start_lon'] = data['inc_lat'] = data['inc_lon'] = data['hosp_lat'] = data['hosp_lon'] = None

        # 2. معلومات البلاغ الأساسية
        report_num = re.search(r"رقم البلاغ\s*(\d+)", full_text)
        data['رقم البلاغ'] = report_num.group(1) if report_num else "N/A"

        national_id = re.search(r"رقم الهوية الإقامة:\s*(\d+)", full_text)
        data['رقم الهوية/الإقامة'] = national_id.group(1) if national_id else "N/A"

        patient_name = re.search(r"الأسم:\s*([^\n]+)", full_text) or re.search(r"معلومات الترحيل\s*\n\s*([^\n]+)", full_text)
        data['اسم المريض'] = patient_name.group(1).strip() if patient_name else "N/A"

        age = re.search(r"العمر:\s*([^\n]+)", full_text)
        data['العمر'] = age.group(1).strip() if age else "N/A"

        gender = re.search(r"النوع:\s*([^\n]+)", full_text)
        data['الجنس'] = gender.group(1).strip() if gender else "N/A"

        incident_type = re.search(r"نوع البلاغ الفعلي\s*([^\n]+)", full_text) or re.search(r"نوع البلاغ\s*([^\n]+)", full_text)
        data['نوع البلاغ'] = incident_type.group(1).strip() if incident_type else "N/A"

        district = re.search(r"الحي:\s*([^\n]+)", full_text)
        data['الحي'] = district.group(1).strip() if district else "N/A"
        
        city = re.search(r"المدينة:\s*([^\n]+)", full_text)
        data['المدينة'] = city.group(1).strip() if city else "N/A"

        center = re.search(r"المركز:\s*([^\n]+)", full_text)
        data['المركز'] = center.group(1).strip() if center else "N/A"

        team = re.search(r"الفرقة:\s*([^\n]+)", full_text)
        data['الفرقة'] = team.group(1).strip() if team else "N/A"

        # 3. التواقيت الحرجـة
        report_time = re.search(r"وقت البلاغ\s*(\d{2}/\d{2}/\d{4}\s*\d{2}:\d{2}:\d{2})", full_text)
        data['وقت البلاغ'] = report_time.group(1) if report_time else "N/A"

        move_time = re.search(r"وقت التحرك\s*(\d{2}/\d{2}/\d{4}\s*\d{2}:\d{2}:\d{2})", full_text)
        data['وقت التحرك'] = move_time.group(1) if move_time else "N/A"

        arr_scene = re.search(r"وصول الموقع\s*(\d{2}/\d{2}/\d{4}\s*\d{2}:\d{2}:\d{2})", full_text)
        data['وصول الموقع'] = arr_scene.group(1) if arr_scene else "N/A"

        arr_hosp = re.search(r"وصول المستشفى\s*(\d{2}/\d{2}/\d{4}\s*\d{2}:\d{2}:\d{2})", full_text)
        data['وصول المستشفى'] = arr_hosp.group(1) if arr_hosp else "N/A"

        # 4. الطاقم الطبي
        p1 = re.search(r"المسعف الأول\s*\n\s*([^\n]+)", full_text)
        data['المسعف الأول'] = p1.group(1).strip() if p1 else "N/A"

        p2 = re.search(r"المسعف الثاني\s*\n\s*([^\n]+)", full_text)
        data['المسعف الثاني'] = p2.group(1).strip() if p2 else "N/A"

        doc = re.search(r"التوجيه الطبي\s*:\s*([^\n]+)", full_text)
        data['طبيب التوجيه'] = doc.group(1).strip() if doc else "N/A"

        rec_doc = re.search(r"المستشفى\s*\n\s*([^\n]+)", full_text)
        data['طبيب الاستقبال'] = rec_doc.group(1).strip() if rec_doc else "N/A"

        # 5. البيانات الطبية والتأمين
        diag = re.search(r"التشخيص المبدئي\s*\n\s*([^\n]+)", full_text)
        data['التشخيص المبدئي'] = diag.group(1).strip() if diag else "N/A"

        ins_company = re.search(r"الشركة\s*\n\s*([^\n]+)", full_text) or re.search(r"(Tawuniya[^\n]*)", full_text)
        data['شركة التأمين'] = ins_company.group(1).strip() if ins_company else "N/A"

        ins_num = re.search(r"رقم العضوية\s*\n\s*([^\n]+)", full_text)
        data['رقم عضوية التأمين'] = ins_num.group(1).strip() if ins_num else "N/A"

    return data

# واجهة رفع الملفات
uploaded_files = st.file_uploader("قم بسحب وإسقاط تقارير الـ PDF هنا (يمكنك اختيار عدة ملفات)", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    reports_list = []
    for f in uploaded_files:
        try:
            parsed = parse_full_epcr(f)
            parsed['اسم الملف'] = f.name
            reports_list.append(parsed)
        except Exception as e:
            st.error(f"خطأ في معالجة الملف {f.name}: {e}")

    df = pd.DataFrame(reports_list)

    # 1. المؤشرات الرئيسية (KPIs)
    st.subheader("📊 ملخص المؤشرات للتقرير التراكمي")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("إجمالي الحالات", len(df))
    k2.metric("أكثر الأحياء بلاغاً", df['الحي'].mode()[0] if not df['الحي'].empty else "N/A")
    k3.metric("أكثر التشخيصات شيوعاً", df['التشخيص المبدئي'].mode()[0] if not df['التشخيص المبدئي'].empty else "N/A")
    k4.metric("أكثر المراكز استجابة", df['المركز'].mode()[0] if not df['المركز'].empty else "N/A")
    k5.metric("شركات التأمين", df['شركة التأمين'].nunique())

    st.markdown("---")

    # 2. الخريطة التفاعلية
    st.subheader("🗺️ خريطة حركة الإسعاف ومواقع الحالات")
    map_df = df.dropna(subset=['inc_lat', 'inc_lon'])
    
    if not map_df.empty:
        m = folium.Map(location=[map_df.iloc[0]['inc_lat'], map_df.iloc[0]['inc_lon']], zoom_start=12)
        for _, r in map_df.iterrows():
            # نقطة الإسعاف
            folium.Marker([r['start_lat'], r['start_lon']], popup=f"🚑 مركز الإسعاف: {r['المركز']}\nالفرقة: {r['الفرقة']}", icon=folium.Icon(color="blue", icon="ambulance", prefix="fa")).add_to(m)
            # نقطة الحادث
            folium.Marker([r['inc_lat'], r['inc_lon']], popup=f"🤕 حادث - بلاغ: {r['رقم البلاغ']}\nالمريض: {r['اسم المريض']}\nالحي: {r['الحي']}", icon=folium.Icon(color="red", icon="user-md", prefix="fa")).add_to(m)
            # المستشفى
            folium.Marker([r['hosp_lat'], r['hosp_lon']], popup="🏥 مستشفى المواساة الخبر", icon=folium.Icon(color="green", icon="hospital", prefix="fa")).add_to(m)
            # مسار الحركة
            folium.PolyLine([[r['start_lat'], r['start_lon']], [r['inc_lat'], r['inc_lon']], [r['hosp_lat'], r['hosp_lon']]], color="red", weight=2.5, opacity=0.7).add_to(m)
        
        st_folium(m, width=1250, height=520)

    st.markdown("---")

    # 3. عرض البيانات التفصيلية في جداول مبوبة
    st.subheader("📋 تفاصيل البيانات المستخرجة من التقارير")
    
    tab1, tab2, tab3 = st.tabs(["بيانات الحالات والمواقع", "التواقيت والكادر الطبي", "البيانات الطبية والتأمين"])
    
    with tab1:
        st.dataframe(df[['رقم البلاغ', 'اسم المريض', 'رقم الهوية/الإقامة', 'العمر', 'الجنس', 'المدينة', 'الحي', 'نوع البلاغ']])
        
    with tab2:
        st.dataframe(df[['رقم البلاغ', 'المركز', 'الفرقة', 'وقت البلاغ', 'وقت التحرك', 'وصول الموقع', 'وصول المستشفى', 'المسعف الأول', 'المسعف الثاني', 'طبيب الاستقبال']])
        
    with tab3:
        st.dataframe(df[['رقم البلاغ', 'اسم المريض', 'التشخيص المبدئي', 'طبيب التوجيه', 'شركة التأمين', 'رقم عضوية التأمين']])

    # 4. زر التصدير إلى Excel
    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 تحميل التقرير التراكمي الشامل كملف Excel (CSV)",
        data=csv,
        file_name='مواساة_تقرير_الهلال_الأحمر_التراكمي.csv',
        mime='text/csv'
    )
