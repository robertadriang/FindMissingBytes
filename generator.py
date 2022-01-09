def initialize_generator_power(start_number):
    """Set the start upper limit of the generator

    :param start_number: The start value of the generator
    :return: The lowest power bigger than the number given
    """
    power = 1
    while 256 ** power <= start_number:
        power += 1
    return power


def byte_generator(start, stop):
    """A generator that yields returns a number converted to a bytestring.
    It generates all bytes starting from the start value until stop (e.g. between 0 and 256^2
    It will return all bytes from x\00 to x\ff\xff, by returning first all the 1-byte sequences
     then all the 2-byte sequence. (Including both x\00 and x\00\x00)

    :param start: The first value that will be converted to a bytestring
    :param stop: The upper limit (Will not be returned by the generator)
    """
    number = start
    power = initialize_generator_power(number)
    reset_number = False
    while number < stop:
        while 256 ** power <= number:
            power += 1
            reset_number = True
        if power != 1 and reset_number:
            number = 0
            reset_number = False
        yield number.to_bytes(power, 'big')
        number += 1