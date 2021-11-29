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
import zipfile
import itertools

def trim_archive(archive,x):
    copy_name=f"truncated_archive.{archive.split('.')[-1]}"
    shutil.copyfile(archive,copy_name) #create a copy of the archive
    f=open(copy_name,'r+b')
    f_size=f.seek(0,2)
    f.seek(f_size-x,0)
    print("#",f.read(x))
    f.seek(f_size - x, 0)
    f.truncate()
    f.close()
    return copy_name


def get_hash(file,hash_type):
    m=hashlib.new(hash_type)
    with open(file, 'rb') as f:
        while chunk := f.read(1024):
            m.update(chunk)
    return m.hexdigest()


def get_hash_zip(file,hash_type):
    m=hashlib.new(hash_type)
    while chunk := file.read(1024):
        m.update(chunk)
    return m.hexdigest()


def append_bits_to_file(file,bits):
    f=open(file,'ab')
    f.write(bits)
    f.close()


def generate_byte_string(length):
    all_bytes=[e.to_bytes(1,'big') for e in range(256)]
    if length==1:
        return all_bytes
    else:
        all_n_bytes=[b"".join(e) for e in itertools.product(all_bytes,repeat=length)]


def byte_generator(n):
    num=0
    while num<n:
        i=1
        while 256**i<=num:
            i+=1
        print(i)
        yield num.to_bytes(i,'big')
        num+=1


BITS_TRIMMED=3
corrupted_archive=trim_archive("./the.zip",BITS_TRIMMED)
generator=byte_generator(256**10)

hash=get_hash("CryptoBasics.pdf",'md5')
print(hash)
print(corrupted_archive)


z=zipfile.ZipFile(corrupted_archive)
f=z.open('CryptoBasics.pdf')
hash2=get_hash_zip(f,'md5')
print(hash2)


