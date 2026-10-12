"""Extrai o conteúdo do build offline legado (HTML único) para src/data/_extracted.json.
Uso único, mantido para rastreabilidade: python3 -I scripts/extract_legacy.py legado.html"""
import re,json,sys
from bs4 import BeautifulSoup
html=open(sys.argv[1],encoding='utf8').read()
def clean(t): return re.sub(r'\s+',' ',t.replace('(abre em outra aba)','')).replace(' ↗','').strip()
def links(node): return [{'title':clean(a.get_text(' ')),'href':a['href']} for a in node.find_all('a')]
chs=[]
for m in re.finditer(r'<template id="offline-[a-z\-]+">(.*?)</template>',html,re.S):
    art=BeautifulSoup(m.group(1),'html.parser').find('article')
    cid=art['data-reader']; op=art.find(class_='reader-opening')
    mins=int(re.search(r'(\d+)\s*min',op.find(class_='section-id').get_text()).group(1))
    concept=art.find(class_='chapter-concept'); photo=art.find(class_='chapter-photo')
    sections=[]
    for s in art.find_all('section',class_='lesson-section'):
        d={'id':s['id'],'evidence':s.find(class_='evidence-label').get_text(strip=True),'title':s.find('h2').get_text(strip=True),'body':s.find('p',recursive=False).get_text(' ',strip=True)}
        for layer in ('more','deep'):
            det=s.find('details',attrs={'data-layer':layer}); d[layer]=det.find('p').get_text(' ',strip=True) if det else None
            f=det.find('figure',class_='equation') if det else None
            if f: d['equation']={'formula':f.find('div').get_text(strip=True),'caption':f.find('figcaption').get_text(strip=True),'layer':layer}
        d['sources']=links(s.find(class_='lesson-sources')); sections.append(d)
    rs=art.find(class_='reader-references')
    ch={'id':cid,'minutes':mins,'title':op.find('h1').get_text(strip=True),'intro':op.find(class_='reader-intro').get_text(strip=True),'idea':op.find(class_='reader-idea').find('p').get_text(strip=True),
        'concept':concept['class'][1] if concept else None,'sections':sections,'refs':links(rs),'refNote':rs.find('p').get_text(strip=True),'refHeading':rs.find('h2').get_text(strip=True),
        'checkTitle':art.find(class_='chapter-check').find('h2').get_text('|',strip=True)}
    if photo:
        ch['photo']={'alt':photo.find('img').get('alt'),'caption':clean(photo.find('figcaption').get_text(' '))}
    chs.append(ch)
soup=BeautifulSoup(re.sub(r'<template.*?</template>','',html,flags=re.S),'html.parser')
rows=[{'id':r['data-journey'],'title':r.select_one('.chapter-title').get_text(strip=True),'teaser':r.select_one('.chapter-teaser').get_text(strip=True),'summary':r.select_one('.chapter-body p').get_text(strip=True),'aside':r.select_one('.chapter-body aside').get_text(strip=True)} for r in soup.select('.chapter-row')]
cred=[{'kind':f.select_one('.meta').get_text(strip=True),'title':f.select_one('h3').get_text(strip=True),'caption':f.select_one('p').get_text(strip=True),'credit':f.select_one('.credit-line').get_text(strip=True),'href':f.find('a')['href'],'alt':f.find('img')['alt']} for f in soup.select('.image-credits figure')]
idx=[{'title':clean(a.get_text(' ')),'href':a['href']} for a in soup.select('.reference-index a')]
json.dump({'chapters':chs,'rows':rows,'credits':cred,'refIndex':idx},open('src/data/_extracted.json','w'),ensure_ascii=False,indent=1)
for c in chs: print(c['id'],c['minutes'],c['concept'],'photo' if 'photo' in c else '',[s['evidence'] for s in c['sections']],[('eq' if 'equation' in s else '') for s in c['sections']])
print(len(rows),len(cred),len(idx))
for c in chs:
    if 'photo' in c: print(c['id'],c['photo']['caption'][:300])
