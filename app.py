import streamlit as st
import pandas as pd
import json
import google.generativeai as genai

# إعداد مفتاح الـ API
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

def extract_data_with_ai(pdf_file):
    # استخدام موديل رؤية وتحليل المستندات
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = """
    قم بتحليل ملف الـ PDF المرفق واستخرج البيانات التالية بدقة على شكل JSON فقط بنفس المفاتيح المحددة:
    {
      "رقم البلاغ": "",
      "التاريخ": "",
      "وقت البلاغ": "",
      "اسم المريض": "",
      "رقم الهوية": "",
      "العمر": "",
      "الجنس": "",
      "المدينة": "",
      "الحي": "",
      "الشكوى الرئيسية": "",
      "التشخيص المبدئي": "",
      "الموجه الطبي": "",
      "اسم المسعف الأول": "",
      "اسم المسعف الثاني": "",
      "إحداثيات مركز الإسعاف": {"lat": null, "lon": null},
      "إحداثيات موقع الحادث": {"lat": null, "lon": null},
      "إحداثيات المستشفى": {"lat": null, "lon": null}
    }
    """
    
    # تحويل الملف المرفوع لرفعه للموديل
    pdf_bytes = pdf_file.read()
    response = model.generate_content([
        {"mime_type": "application/pdf", "data": pdf_bytes},
        prompt
    ])
    
    # تنظيف واستخراج الـ JSON
    clean_json = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_json)
