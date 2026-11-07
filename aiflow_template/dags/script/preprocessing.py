# 1. add unicodedata, re, psycopg
# 2. create main function
# 3. create clean tag function
# 4. create ingestion function
# 5. select data from bronze, then insert to silver

# def clean_content(content):
#     content_list = []
#     exclude = [
#         "Berlangganan untuk dapatkan pos terbaru lewat email."
#         "Langganan sekarang agar bisa terus membaca dan mendapatkan akses ke semua arsip."
#         ".Lanjutkan membaca"
#         "baca juga-"
#     ]
    
#     for kalimat in content.split("."):
#         text = content.replace("\u201d", "")
#         text = content.replace("Baca Juga", "")
#         text = text.replace("\u201c", "")

#     for excl in exclude:
#         if excl.lower() not in text.lower():
#             content_list.append(text)

#     return " ".join(content_list)
    