from pathlib import Path
import json,math
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Image,Table,TableStyle,PageBreak,Flowable
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parent
P=ROOT/'v3 - Two-sided Assembly';M=ROOT/'v4 - Metal Production'
for name,file in [('Body','Arial.ttf'),('Strong','Arial Bold.ttf')]:
    path=Path('/System/Library/Fonts/Supplemental')/file
    if not path.exists():
        import matplotlib
        path=Path(matplotlib.__file__).parent/'mpl-data/fonts/ttf'/('DejaVuSans-Bold.ttf' if name=='Strong' else 'DejaVuSans.ttf')
    pdfmetrics.registerFont(TTFont(name,str(path)))
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleX',fontName='Strong',fontSize=24,leading=29,textColor=colors.HexColor('#18272b'),spaceAfter=9))
styles.add(ParagraphStyle(name='HeadX',fontName='Strong',fontSize=14,leading=18,textColor=colors.HexColor('#213a42'),spaceAfter=9))
styles.add(ParagraphStyle(name='BodyX',fontName='Body',fontSize=9.3,leading=14,spaceAfter=8))
styles.add(ParagraphStyle(name='SmallX',fontName='Body',fontSize=8,leading=11,spaceAfter=6,textColor=colors.HexColor('#4f5e62')))
styles.add(ParagraphStyle(name='Kicker',fontName='Strong',fontSize=9,leading=13,spaceAfter=10,textColor=colors.HexColor('#9b7545')))
W=515

def p(text,kind='BodyX'):return Paragraph(text,styles[kind])
def pic(path,w=515):
    from PIL import Image as PIL
    a=PIL.open(path);return Image(str(path),width=w,height=w*a.height/a.width)
def table(rows,widths=None):
    data=[[p(str(x),'SmallX') for x in row] for row in rows]
    t=Table(data,colWidths=widths or [W/len(rows[0])]*len(rows[0]),hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7edef')),('VALIGN',(0,0),(-1,-1),'TOP'),
      ('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#89989c')),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#d9dfe0')),
      ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    return t

def footer(c,doc):
    c.setStrokeColor(colors.HexColor('#c6cfd1'));c.line(40,36,555,36)
    c.setFillColor(colors.HexColor('#68787c'));c.setFont('Body',7)
    c.drawString(40,23,'polukal  |  Blades of Chaos  |  nominal dimensions in mm  |  2026-09-15')
    c.drawRightString(555,23,f'{doc.page}')

def build(path,story):
    doc=SimpleDocTemplate(str(path),pagesize=(595.28,841.89),rightMargin=40,leftMargin=40,topMargin=36,bottomMargin=49,
                         title=path.stem,author='polukal',pageCompression=1)
    doc.build(story,onFirstPage=footer,onLaterPages=footer)

def arrow(c,x1,y1,x2,y2,label,vertical=False):
    c.setStrokeColor(colors.HexColor('#42565d'));c.setFillColor(colors.HexColor('#42565d'));c.setLineWidth(.5);c.line(x1,y1,x2,y2)
    angle=math.atan2(y2-y1,x2-x1)
    for x,y,a in [(x1,y1,angle),(x2,y2,angle+math.pi)]:
        q=c.beginPath();q.moveTo(x,y);q.lineTo(x+5*math.cos(a+.35),y+5*math.sin(a+.35));q.lineTo(x+5*math.cos(a-.35),y+5*math.sin(a-.35));q.close();c.drawPath(q,fill=1,stroke=0)
    c.setFont('Body',9)
    if vertical:
        c.saveState();c.translate(x1+13,(y1+y2)/2);c.rotate(90);c.drawCentredString(0,0,label);c.restoreState()
    else:c.drawCentredString((x1+x2)/2,y1+7,label)

class PlanView(Flowable):
    def __init__(self,data,metal=False):super().__init__();self.width=W;self.height=305;self.data=data;self.metal=metal
    def draw(self):
        c=self.canv;s=4.0;ox=24;oy=65;outline=self.data['outline'];h=max(y for x,y in outline)
        c.setFont('Strong',11);c.drawString(24,286,'NOMİNAL ÜST GÖRÜNÜŞ' if self.metal else 'A HALF - MATING FACE / SOCKET LOCATIONS')
        q=c.beginPath();q.moveTo(ox+outline[0][0]*s,oy+outline[0][1]*s)
        for x,y in outline[1:]:q.lineTo(ox+x*s,oy+y*s)
        q.close();c.setFillColor(colors.HexColor('#edf0ef'));c.setStrokeColor(colors.HexColor('#253b42'));c.setLineWidth(.65);c.drawPath(q,fill=1,stroke=1)
        if self.metal:
            ring=self.data['eyelet_loop'];cx=sum(x for x,y in ring)/len(ring);cy=sum(y for x,y in ring)/len(ring)
        else:cx,cy=self.data['eyelet_center']
        c.setFillColor(colors.white);c.circle(ox+cx*s,oy+cy*s,2.3*s,fill=1,stroke=1)
        if not self.metal:
            centers=json.loads((P/'validation.json').read_text())['front_half']['key_centers_xy_mm']
            for i,(x,y) in enumerate(centers,1):
                c.setFillColor(colors.white);c.circle(ox+x*s,oy+y*s,1.45*s,fill=1,stroke=1);c.setFillColor(colors.HexColor('#42565d'));c.setFont('Strong',8);c.drawCentredString(ox+x*s,oy+y*s-(28 if i==1 else 20),f'K{i}')
        c.setStrokeColor(colors.HexColor('#8b989d'));c.setLineWidth(.4)
        for x in [ox,ox+110*s]:c.line(x,oy-5,x,30)
        arrow(c,ox,35,ox+110*s,35,'110.00 ±0.30' if self.metal else '110.00')
        c.line(ox+110*s,oy,ox+110*s+25,oy);c.line(ox+110*s,oy+h*s,ox+110*s+25,oy+h*s)
        arrow(c,ox+110*s+14,oy,ox+110*s+14,oy+h*s,f'{h:.2f}'+(' ±0.30' if self.metal else ''),True)
        c.line(ox+cx*s,oy+cy*s+2.3*s,ox+cx*s+20,255);c.line(ox+cx*s+20,255,220,255)
        c.setFont('Body',9);c.drawString(75,261,'Ø4.60 +0.20 / 0 bitmiş delik' if self.metal else 'Ø4.60 keyring opening')
        c.setFont('Body',8);c.drawString(24,6,'Ölçeksiz görünüş. Yazılı ölçüler ve 3D model esas alınır.' if self.metal else 'Views are not to scale. Use stated dimensions and supplied 3D geometry.')

class SideView(Flowable):
    def __init__(self,profile,gap=0,label='ASSEMBLED SIDE ENVELOPE'):
        super().__init__();self.width=W;self.height=130;self.profile=profile;self.gap=gap;self.label=label
    def draw(self):
        c=self.canv;s=4;ox=24;oy=64;h=max(z for x,z in self.profile)+self.gap/2
        c.setFont('Strong',10);c.drawString(24,113,self.label)
        q=c.beginPath();x,z=self.profile[0];q.moveTo(ox+x*s,oy+(z+self.gap/2)*s)
        for x,z in self.profile:q.lineTo(ox+x*s,oy+(z+self.gap/2)*s)
        for x,z in self.profile[::-1]:q.lineTo(ox+x*s,oy-(z+self.gap/2)*s)
        q.close();c.setStrokeColor(colors.HexColor('#263d44'));c.setFillColor(colors.HexColor('#eef0ef'));c.drawPath(q,fill=1,stroke=1)
        c.setDash(3,2);c.line(ox-4,oy,ox+445,oy);c.setDash()
        arrow(c,ox+460,oy-h*s,ox+460,oy+h*s,f'{2*h:.2f}',True)
        c.setFont('Body',8);c.drawString(24,10,'İki dış yüzey de detaylıdır. Eksen çizgisi simetri düzlemini gösterir.' if 'TEK PARÇA' in self.label else 'Both external faces carry the sculpt. Center line is the symmetry / joining plane.')

class KeySection(Flowable):
    def __init__(self):super().__init__();self.width=W;self.height=240
    def draw(self):
        c=self.canv;sc=42;ox=145;oy=110;gap=.08
        c.setFont('Strong',11);c.drawString(15,222,'SECTION THROUGH ALIGNMENT KEY (ENLARGED)')
        for sign in [1,-1]:
            points=[(-2.3,sign*gap/2),(-1.45,sign*gap/2),(0,sign*(1.566+gap/2)),(1.45,sign*gap/2),(2.3,sign*gap/2),(2.3,sign*2.15),(-2.3,sign*2.15)]
            q=c.beginPath();q.moveTo(ox+points[0][0]*sc,oy+points[0][1]*sc)
            for x,y in points[1:]:q.lineTo(ox+x*sc,oy+y*sc)
            q.close();c.setFillColor(colors.HexColor('#dce4e5'));c.setStrokeColor(colors.HexColor('#60777e'));c.drawPath(q,fill=1,stroke=1)
        points=[(-.5,-.7),(.5,-.7),(1.2,0),(.5,.7),(-.5,.7),(-1.2,0)]
        q=c.beginPath();q.moveTo(ox+points[0][0]*sc,oy+points[0][1]*sc)
        for x,y in points[1:]:q.lineTo(ox+x*sc,oy+y*sc)
        q.close();c.setFillColor(colors.HexColor('#bc9157'));c.drawPath(q,fill=1,stroke=1)
        c.setFillColor(colors.HexColor('#42565d'));c.setFont('Body',9)
        for y,line in zip([190,172,154,136,118,100,82,64,46],[
          '3 identical keys per finished blade','Key: Ø2.40 max × 1.40 long','Tip flats: Ø1.00','Socket mouth: Ø2.90','Socket depth: 1.566','Socket roof: 47.2°','Nominal radial clearance: 0.25','Preview adhesive gap: 0.08','Remaining skin: at least 1.06']):c.drawString(265,y,line)
        c.setFont('Body',8);c.drawString(15,5,'Bonding faces touch for a flush joint. The 0.08 mm gap is a visualization allowance, not a built-in spacer.')

pr=json.loads((P/'validation.json').read_text());pd=json.loads((P/'drawing-data.json').read_text())
metal=json.loads((M/'metal-validation.json').read_text());md=json.loads((M/'drawing-data.json').read_text())
npz=np.load(M/'metal_casting_master.mesh.npz');v=npz['vertices'];mid=np.ptp(v[:,2])/2
profile=[]
for x in np.arange(0,110.001,.25):
    z=v[np.abs(v[:,0]-x)<.26,2];profile.append([float(x),float(z.max()-mid) if len(z) else .9])

story=[p('POLUKAL / FABRICATION SET V3','Kicker'),p('Blades of Chaos','TitleX'),p('110 mm two-sided printable keychain','HeadX'),
 p('Print one A front and one mirrored B back for each finished blade. Both halves sit on their bonding faces with the sculpt facing up. For a pair of blades, print two A halves and two B halves.'),pic(P/'assembled-preview.png'),Spacer(1,10),
 table([['Part','File','Per blade'],['Front half A','blade_A_front.stl','1'],['Mirrored back B','blade_B_back_mirrored.stl','1'],['Double-taper alignment key','alignment_key.stl','3']], [100,345,70]),Spacer(1,12),
 p('Ready-arranged plates','HeadX'),p('<b>output_model.3mf / .stl:</b> one A + one B + five keys (two spare).<br/><b>two_blades_print_plate.3mf:</b> four halves + eight keys (two spare).'),
 p('Assembled size: 110 × 38.28 × 11.93 mm, including the illustrated 0.08 mm bond line. Keyring hole: Ø4.60 mm. The reference assembly file is for inspection; the arranged plates contain the printing orientations.','SmallX'),PageBreak(),
 p('Geometry and fit','TitleX'),PlanView(pd),SideView(pd['half_side_profile'],.08),KeySection(),PageBreak(),
 p('Print, fit and bond','TitleX'),pic(P/'exploded-preview.png',490),Spacer(1,8),
 p('<b>1. Print.</b> Use the supplied orientation, flat bonding face on the bed, supports off. Start with a calibrated 0.25 mm nozzle / 0.10 mm layer profile for the small detail. A 0.4 mm nozzle retains the main shape but softens the fine ornament. Use 4 walls, 5 bottom layers, 6 top layers and about 30% infill.'),
 p('<b>2. Prepare.</b> Remove any brim from the tiny keys and clean the bonding faces. Keep the conical sockets clear. Lightly flatten a warped seam face before assembly; preserve the socket mouths.'),
 p('<b>3. Dry-fit.</b> Place three keys in A. Flip B over around its Y axis so its flat face mates with A. Match the pommel hole and outer profile. The keys are loose alignment aids; apply light clamping rather than forcing the fit.'),
 p('<b>4. Bond.</b> Apply a thin, even layer of adhesive compatible with the printed material to the flat lands, seat B, and clamp until the adhesive manufacturer’s full cure time. Clear squeeze-out from the eyelet and outline.'),
 p('<b>5. Finish.</b> Dress the seam, prime and paint if desired, then fit a metal split ring. For plastic welding, use matching polymers and trial the seam on a coupon; BONDLINE_GAP=0 represents a flush welded joint.'),
 p('The files pass manifold, winding, mirrored fit, socket skin and print-overhang checks. No physical print, bond-strength test or welding trial has been performed.','SmallX')]
build(P/'Printing_and_Assembly.pdf',story)

story=[p('POLUKAL / METAL ÜRETİM DOSYASI V4','Kicker'),p('Blades of Chaos','TitleX'),p('110 mm anahtarlık - teklif ve ilk numune paketi','HeadX'),
 p('İki yüzü detaylı, tek parça metal döküm modeli. Gövdede yapıştırma hattı veya plastik hizalama yuvaları bulunmaz. Model nominal bitmiş parça ölçülerindedir.'),pic(M/'metal-preview.png'),Spacer(1,10),
 table([['Özellik','Nominal / hedef'],['Boy × en × kalınlık','110.00 × 38.27 × 11.85 mm'],['Anahtarlık deliği','Ø4.60 mm; bitmiş ölçü +0.20 / 0'],['Gövde hacmi / yaklaşık kütle','8.741 cm³ / pirinçte yaklaşık 74 g (8.5 g/cm³ varsayımı)'],['İnce kenar / kontur yuvarlatma','En az 1.80 mm toplam kalınlık / XY R0.30'],['Önerilen görünüm','Antik pirinç / bronz patina; alaşım ve kaplama üreticiyle netleştirilecek']],[180,335]),Spacer(1,12),
 p('Üretici ararken: “hassas döküm / kayıp mum döküm / takı-aksesuar dökümü” yapabilen atölye. İlk teklif için yüksek detaylı STL ve bu PDF birlikte verilmeli. Görsel, önerilen yüzey görünümünü gösterir.','SmallX'),PageBreak(),
 p('Nominal teknik görünüşler','TitleX'),PlanView(md,True),SideView(profile,0,'TEK PARÇA METAL - YAN ZARF GÖRÜNÜŞÜ'),Spacer(1,12),
 table([['Kontrol','Bitmiş parça hedefi'],['Toplam boy / en / kalınlık','110.00 ±0.30 / 38.27 ±0.30 / 11.85 ±0.30 mm'],['Delik','Ø4.60 +0.20 / 0 mm; gerekirse döküm sonrası işleme'],['Yüzey ve kenarlar','Çapak ve sivri uç olmadan; ince motifler korunarak finisaj'],['Profil / rölyef','Ana STL geometrisi esas; küçük ikincil izlerin korunması ilk numunede değerlendirilecek']],[175,340]),Spacer(1,8),
 p('Ölçüler mm. Çizim üzerinden ölçü alınmamalı. Toleranslar teklif ve numune hedefidir; seçilen alaşım, döküm ve finisaj kapasitesiyle üretici tarafından teyit edilmelidir.','SmallX'),PageBreak(),
 p('Üretim notları ve teklif metni','TitleX'),
 p('1 / Dosyaların kullanımı','HeadX'),
 p('<b>metal_casting_master.stl / .3mf:</b> 495.248 üçgenli, kapalı, tek gövdeli ana üretim geometrisi. Detaylı mum/dökülebilir reçine master için esas dosyadır.<br/><b>metal_CAD_interchange.step:</b> 65.000 yüzeyli fasetli B-rep CAD aktarım modeli. 30.000 örnekte ana yüzeye göre en büyük ölçülen fark 0.047 mm; bu değer tüm yüzey için matematiksel hata üst sınırı değildir.<br/><b>metal_outline_REFERENCE_ONLY.dxf:</b> mm biriminde plan konturu; ölçüm ve teklif referansı. Üç boyutlu rölyef STL’den alınır.'),
 p('2 / Önerilen proses ve sorumluluklar','HeadX'),
 p('Başlangıç prosesi: uygun mum/dökülebilir reçine master ile kayıp mum hassas döküm. Antik pirinç/bronz görünümü hedeflenmiştir; döküme uygun alaşım kodu ve nihai kaplama üretici tarafından önerilmelidir. Aynı hacmin alüminyum karşılığı yaklaşık 24 g’dır; hafiflik istenirse ayrı alternatif tekliflenebilir.'),
 p('Model 1:1 nominal bitmiş parçadır. Evrensel bir büzülme payı uygulanmamıştır. Üretici; alaşım/proses için çekme telafisini, yolluk-besleme ve havalandırmayı, master desteklerini, parlatma ve kaplama paylarını kendi prosesiyle belirler. Yolluk bağlantısı rölyefli yüzlere zarar vermeyecek bölgede seçilir.'),
 p('Ana oyma çizgileri yaklaşık 0.52 mm genişlik ve 0.28 mm derinliktedir; daha ince ikincil izler de vardır. Aşırı parlatma bu detayları silebilir. Önce tek numunede motif okunurluğu, delik ölçüsü, yüzey, kütle ve eldeki görünüm değerlendirilir.'),
 p('3 / Üreticiye gönderilecek kısa metin','HeadX'),
 p('Merhaba, ekte iki yüzü detaylı, 110 mm uzunluğunda tek parça metal anahtarlık modeli bulunmaktadır. Kayıp mum / hassas döküm ile bir ilk numune için teklif rica ederim. Antik pirinç-bronz görünümüne uygun alaşım, patina/kaplama ve finisaj önerinizi paylaşabilir misiniz?'),
 p('Lütfen master/kalıp gibi tek seferlik maliyetleri, numune ücretini, 10 / 50 / 100 adet için birim fiyatı, minimum siparişi ve termin süresini ayrı belirtiniz. Bu adetler fiyat karşılaştırması içindir. Ölçü hedefleri ve ince rölyeflerin prosesinizle korunabilirliğini değerlendirmenizi rica ederim. Seri üretim kararı numune incelemesinden sonra verilecektir.'),
 p('Proses kaynakları: <link href="https://formlabs.com/support/Introduction-to-casting-with-Formlabs-resins/" color="#356575">Formlabs - Introduction to casting</link>; <link href="https://formlabs.com/global/industries/jewelry/" color="#356575">Formlabs - jewelry pattern workflow</link>. Süreç önerisi bu kaynaklar ve model geometrisine dayalı mühendislik değerlendirmesidir.','SmallX'),
 p('Dosyalar geometrik olarak doğrulanmıştır. Fiziksel döküm numunesi veya üretici proses onayı henüz alınmamıştır.','SmallX')]
build(M/'Metal_Sanayi_Uretim_Paketi_TR.pdf',story)
print('Created both handoff PDFs.')
