from rarfile import RarFile
if -1:
    print("Truthy")
#
# with RarFile('AI_PROJECT.rar') as file:
#     file.extract(file.namelist()[0])
#
z=RarFile('AI_PROJECT.rar')
f=z.open('AI_PROJECT/news.json')
print(f.read())
#
#  try:
#         z = zipfile.ZipFile(archive)
#         f = z.open(file_name)
#         computed_hash = compute_hash_opened_file(f, hash_method)
#         if computed_hash == file_hash:
#             return True
#         return False
# except Exception as e:
#         # TODO check other exception type
#         # BadZipFile when the archive is corrupted
#         # Errno 22 when the archive is valid but the file inside is corrupted
#         if type(e).__name__ == 'BadZipFile' or '[Errno 22]' in str(e):
#             pass
#         else:
#             print("@@@@ NEW ERROR FOUND @@@@")
#             print(e)
#             print(archive)
#             traceback.print_exc()
#             exit()
# finally:
#     trim_archive(archive, added_bytes_length)