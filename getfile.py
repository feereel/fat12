from collections import namedtuple

FILE = "fattask.9f81.img"
#FILE = "disk.img"

Boot = namedtuple('Bootinfo', 'jmp firm byte_in_sect sect_in_clas reserv_sects fat_table_c root_files sect_in_razd disk_type sect_count hidd_sect_c')
File = namedtuple('Files', 'name extention attr claster size')

def get_boot_info(data):
    jmp = data[0:3]
    firm = data[3:11]
    byte_in_sect = int.from_bytes(data[11:13], byteorder='little', signed=True)
    sect_in_clas = int.from_bytes(data[13:14], byteorder='little', signed=True)
    reserv_sects = int.from_bytes(data[14:16], byteorder='little', signed=True)
    fat_table_c = int.from_bytes(data[16:17], byteorder='little', signed=True)
    root_files = int.from_bytes(data[17:19], byteorder='little', signed=True)
    sect_in_razd = data[19:21]
    disk_type = data[21]
    sect_count = int.from_bytes(data[22:23], byteorder='little', signed=True)
    # Число секторов на дорожке (для прерывания 0x13)
    # Число рабочих поверхностей (для прерывания 0x13)
    hidd_sect_c = data[0x1C:0x1C+4]
    # Общее число секторов в разделе. Поле используется, если в разделе свыше 65535 секторов, в противном случае поле содержит 0.    
    
    info = {"Джамп": jmp,
            "Фирма": firm, 
            "Байтов в секторе": byte_in_sect,
            "Секторов в кластере": sect_in_clas, 
            "Число резервных секторов в резервной области раздела, начиная с первого сектора раздела": reserv_sects,
            "Число таблиц (копий) FAT": fat_table_c, 
            "Количество 32-байтных дескрипторов файлов в корневом каталоге":root_files, 
            "Общее число секторов в разделе": sect_in_razd, 
            "Тип носителя. Для жесткого диска имеет значение 0xF8; для гибкого диска (2 стороны, 18 секторов на дорожке) – 0xF0": disk_type,
            "Количество секторов, занимаемых одной копией FAT": sect_count,
            "Число скрытых секторов перед разделом": hidd_sect_c}
    
    for name, val in info.items():
        print(f"{name}: {val}")
        
    
    boot_info = Boot(jmp, firm, byte_in_sect, sect_in_clas, reserv_sects, fat_table_c, root_files, sect_in_razd, disk_type, sect_count, hidd_sect_c)
    return boot_info

def get_files(data, root, root_size):
    res = []
    
    for i in range(root, root+root_size, 32):
        name = data[i:i+8]
        extention = data[i+8:i+11]
        attr = int.from_bytes(data[i+11:i+12], byteorder='little', signed=True)
        # 1 Зарезервировано для Windows NT. Поле обрабатывается только в FAT32
        # 1 Поле, уточняющее время создания файла (содержит десятки миллисекунд). Поле обрабатывается только в FAT32
        # 1 Время создания файла. Поле обрабатывается только в FAT32
        # 2 Дата создания файла. Поле обрабатывается только в FAT32 
        # 2 Дата последнего обращения к файлу для записи или считывания данных. Поле обрабатывается только в FAT32
        # 2 Старшее слово номера первого кластера файла. Поле обрабатывается только в FAT32
        # 2 Время выполнения последней операции записи в файл
        # 2 Дата выполнения последней операции записи в файл
        claster = int.from_bytes(data[i+26:i+28], byteorder='little', signed=True)
        size =  int.from_bytes(data[i+28:i+32], byteorder='little', signed=True)
        
        file_desc = File(name, extention, attr, claster, size)
        res.append(file_desc)
    return res

def get_fat_table(data, fat_addr, fat_size):
    res = []
    for i in range(fat_addr, fat_addr + fat_size, 3):
        b1, b2, b3 = data[i], data[i+1], data[i+2]
        res.append(b1 + ((b2 % 16) << 8))
        res.append((b2 >> 4) + (b3 << 4))
    return res

def read_file(data, clas_start, fat_table, clas_size, file_desc):
    if file_desc.attr != 0x20:
        return b''
    if file_desc.name[0:1] == b'\xe5':
        return b''
    
    out = b''
    claster_id = file_desc.claster
    while claster_id != 0xFFF and claster_id > 0:
        offset = (claster_id - 2)*clas_size
        out += data[clas_start + offset: clas_start + offset + clas_size]
        claster_id = fat_table[claster_id]
    return out[:file_desc.size]
        

if __name__ == "__main__":
    disk = open(FILE, 'rb')
    data = disk.read()
    
    boot_info = get_boot_info(data)
    
    clas_size = boot_info.byte_in_sect * boot_info.sect_in_clas
    
    fat_addr = boot_info.byte_in_sect * boot_info.reserv_sects
    fat_size = boot_info.sect_count * boot_info.byte_in_sect
    
    root_addr = boot_info.byte_in_sect * (boot_info.reserv_sects + (boot_info.fat_table_c * boot_info.sect_count))
    root_size = boot_info.root_files * 32
    clas_start = root_addr + root_size
    
    #print(fat_addr, root_addr, clas_start)

    files_desc = get_files(data, root_addr, root_size)
    
    # for file in files_desc:
    #     print(file.name, file.claster)
    
    fat_table = get_fat_table(data, fat_addr, fat_size)     
    #print(fat_table)
    
    sum_file = open('sum_file', 'wb')
    for file in files_desc:
        content = read_file(data, clas_start, fat_table, clas_size, file)
        if content:
            filename = './fat12/'
            filename += file.name.decode().replace(' ', '').lower()
            filename += '.'
            filename += file.extention.decode().replace(' ', '').lower()
            with open(filename, 'wb') as out:
                sum_file.write(content)
                out.write(content)
    
    sum_file.close()    
    disk.close()