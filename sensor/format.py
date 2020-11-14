class NumberFormat:
    def __init__(self, sign, int_bytes, dec):
        self.sign = sign
        self.int_bytes = int_bytes
        self.dec = dec

    def read(self, data):
        print(data)
        return self.read_int(data) + self.read_dec(data)

    def read_int(self, data):
        bytes = data[0:self.int_bytes]
        sign = 1
        if self.sign and bytes[-1] & 0x80 != 0:
            sign = -1
            bytes[-1] &= ~0x80
        return sum(
            byte << (index * 8)
            for (index, byte) in enumerate(bytes)
        ) * sign

    def read_dec(self, data):
        if not self.has_dec:
            return 0
        return data[self.int_bytes] / 10 ** self.dec

    def write(self, num):
        return [
            *self.write_int(num),
            *self.write_dec(num)
        ]

    def write_int(self, num):
        n = int(abs(num))
        bytes = [
            n >> (8 * index) & 0xff
            for index in range(self.int_bytes)
        ]
        if self.sign and num < 0:
            bytes[-1] |= 0x80
        return bytes

    def write_dec(self, num):
        if self.has_dec:
            n = abs(num) - int(abs(num))
            return [
                int(n * 10 ** self.dec)
            ]
        return []

    @property
    def has_dec(self):
        return self.dec > 0

    @property
    def dec_bytes(self):
        return 1 if self.has_dec else 0

    def __len__(self):
        return self.int_bytes + self.dec_bytes


def signed(i=1, dec=0):
    return NumberFormat(True, i, dec)


def unsigned(i=1, dec=0):
    return NumberFormat(False, i, dec)
