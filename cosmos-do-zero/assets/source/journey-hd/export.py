"""Run with Python, Pillow, NumPy and SciPy. Reads only archived local inputs."""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
from paint import render

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / 'public/renders/journey-hd'
CC = 'CC BY 4.0'
ESO = 'ESO/M. Kornmesser'
PREFIX = '/renders/journey-hd/'
M51 = json.loads((HERE.parent / 'm51.json').read_text(encoding='utf-8'))


def original(caption):
    return (None, 'illustration', caption, 'Cosmos do Zero', 'Material autoral do projeto', '')


plates = {
    'primordial': original('Plasma quente ocupando todo o quadro. A textura e as cores ilustram a fase densa do Universo.'),
    'nucleosynthesis': original('Núcleo de hélio-4 ampliado. Duas cores distinguem os dois prótons e os dois nêutrons nesta representação esquemática.'),
    'cmb': ('ilc_9yr_moll4096.png','observation','Mapa do céu inteiro obtido com nove anos de observações do WMAP. As cores representam diferenças de temperatura na radiação cósmica de fundo.','NASA/WMAP Science Team','NASA Media Usage Guidelines','https://science.nasa.gov/mission/wmap/wmap-overview/'),
    'dark-ages': original('Gás neutro antes das primeiras estrelas. A iluminação em falsa cor torna visíveis as regiões mais densas nesta ilustração.'),
    'first-stars': ('eso1524a.jpg','illustration','Impressão artística da galáxia CR7. O brilho de um grupo de estrelas jovens ilustra como poderiam aparecer as primeiras gerações estelares.',ESO,CC,'https://www.eso.org/public/images/eso1524a/'),
    'reionization': ('eso1138a.jpg','illustration','Galáxias jovens entre regiões de hidrogênio ainda neutro, numa reconstrução artística do fim da reionização.',ESO,CC,'https://www.eso.org/public/images/eso1138a/'),
    'acceleration': ('heic2018a.jpg','observation','NGC 2525, onde o Hubble acompanhou a supernova de tipo Ia SN 2018gv. Supernovas dessa classe permitem comparar distâncias e investigar a expansão.','ESA/Hubble & NASA, A. Riess and the SH0ES team. Agradecimento a Mahdi Zamani.',CC,'https://esahubble.org/news/heic2018/'),
    'solar-system': ('eso1436f.jpg','illustration','Reconstrução artística de uma estrela jovem envolta por um disco de gás e poeira, cenário análogo à formação do Sistema Solar.','ESO/L. Calçada',CC,'https://www.eso.org/public/images/eso1436f/'),
    'earth': original('Terra jovem com material incandescente entre regiões de crosta em resfriamento. A superfície é uma reconstrução artística.'),
    'oxygen': ('soudan.jpg','observation','Camadas ricas em ferro no afloramento de Soudan, Minnesota, com cerca de 2,69 bilhões de anos. Essas rochas registram a química dos oceanos antes do grande acúmulo de oxigênio atmosférico.','James St. John','CC BY 2.0','https://www.usgs.gov/media/images/minnesota-banded-iron'),
    'present': ('../observed/heic0506a.jpg','observation','A galáxia espiral M51 e sua companheira NGC 5195, observadas pelo Hubble. Faixas de poeira delineiam os braços da espiral.',M51['credit'],CC,M51['href']),
}

downloads = {
    **{key: f'https://cdn.eso.org/images/large/{key}' for key in ['eso1138a.jpg','eso1436f.jpg','eso1524a.jpg']},
    'heic2018a.jpg': 'https://cdn.esahubble.org/archives/images/large/heic2018a.jpg',
    'ilc_9yr_moll4096.png': 'https://assets.science.nasa.gov/content/dam/science/missions/wmap/ilc_9yr_moll4096.png',
    'soudan.jpg': 'https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/thumbnails/image/Jaspilite_banded_iron_formation_%28Soudan_Iron-Formation%2C_Neoarchean%2C_-2.69_Ga%3B_Stuntz_Bay_Road_outcrop%2C_Soudan_Underground_State_Park%2C_Soudan%2C_Minnesota%2C_USA%29_16_%2819225416055%29_0.jpg',
    '../observed/heic0506a.jpg': M51['download'],
}


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest, provenance = [], []
    sheet = Image.new('RGB',(960,4*205),'#0b1018')
    draw = ImageDraw.Draw(sheet)
    for index, (era,(filename,kind,caption,credit,license_name,source)) in enumerate(plates.items()):
        origin = (HERE / (filename or 'paint.py')).resolve()
        input_image = Image.open(origin).convert('RGB') if filename else render(era)
        assert input_image.width >= 1600 and input_image.height >= 900
        method = 'Recorte panorâmico e redução proporcional.'
        if era == 'cmb':
            # Only the connected white background at the corners is replaced.
            for corner in [(0,0),(input_image.width-1,0),(0,input_image.height-1),(input_image.width-1,input_image.height-1)]:
                ImageDraw.floodfill(input_image,corner,(7,12,20),thresh=0)
            frame = ImageOps.pad(input_image,(1600,900),color=(7,12,20),method=Image.Resampling.LANCZOS)
            method = 'Mapa integral; fundo externo escurecido e margens.'
        else:
            frame = ImageOps.fit(input_image,(1600,900),Image.Resampling.LANCZOS,
                                 centering=(.5, .25 if era=='present' else .5))
        row = dict(id=era,kind=kind,caption=caption,credit=credit,source=source,license=license_name,width=1600,height=900)
        variants = []
        for field,width in [('small',880),('large',1600)]:
            height = width*9//16
            path = OUT / f'{era}-{width}.webp'
            frame.resize((width,height),Image.Resampling.LANCZOS).save(path,quality=86,method=5)
            row[field] = PREFIX + path.name
            variants.append(dict(url=row[field],width=width,height=height,bytes=path.stat().st_size,sha256=digest(path)))
        manifest.append(row)
        provenance.append(dict(id=era, input=origin.relative_to(ROOT).as_posix(), inputSize=input_image.size,
                               inputSha256=digest(origin),download=downloads.get(filename,''),source=source,
                               credit=credit,license=license_name,method=method if filename else 'Ilustração original renderizada em CPU na resolução final.',variants=variants))
        x,y = (index%3)*320,(index//3)*205
        with Image.open(path) as delivered:
            sheet.paste(delivered.resize((320,180),Image.Resampling.LANCZOS),(x,y))
        draw.text((x+8,y+184),era,fill='white')
    write_json(OUT/'manifest.json',manifest)
    write_json(HERE/'provenance.json',provenance)
    sheet.save(HERE/'review.jpg',quality=90)


if __name__ == '__main__':
    main()

