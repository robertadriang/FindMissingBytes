# Sa se scrie un tool care primeste un hash pentru un fisier originial si o arhiva trunchiata (maxim “x” bytes de la finalul arhivei originale lipsesc).
# Tool-ul va gasi fisierul original din arhiva ( in momentul in care se va despacheta fisierul din arhiva va avea acelasi hash ca cel primit la input )
# Pentru rezolvarea acestei probleme este imperativ folosirea oricarei forme de paralelizare (
#
# multi threding/multiuprocessing / multi system / etc )
# INPUT:
# Arhiva truncata
# Numele fisierului din arhiva
# Hash-ul expected al fisierului
# Optional ar fi utila si o optiune de trunchiere a unei arhive si generare a datelor de input de
# mai sus.
# OUTPUT:
# Continutul fisierului dupa ce a fost dezarhivat cu success
import hashlib
import shutil

def trim_archive(archive,x):
    copy_name=f"truncated_archive.{archive.split('.')[-1]}"
    shutil.copyfile(archive,copy_name ) #create a copy of the archive
    f=open(copy_name,'r+b')
    f_size=f.seek(0,2)
    f.seek(f_size-x,0)
    f.truncate()
    f.close()
    return copy_name

corrupted_archive=trim_archive("./the.zip",1)
