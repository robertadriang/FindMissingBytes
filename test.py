
def initialize_generator_power(number):
    pow=1
    while 256**pow<=number:
        pow+=1
    return pow


def byte_generator(start,n):
    number=start
    pow=initialize_generator_power(number)
    reset_number=False
    while number<n:
        while 256**pow<=number:
            pow+=1
            reset_number=True
        if pow!=1 and reset_number:
            number=0
            reset_number=False
        print(pow)
        yield number.to_bytes(pow,'big')
        number+=1

generator=byte_generator(196600,1966080)
for i in range(258):
    print(next(generator))