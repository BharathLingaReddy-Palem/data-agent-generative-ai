"""Owner-scoped templates and branded exports built from selected evidence."""
import io
import re
import uuid
from html import escape
import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.colors import HexColor
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from backend.config import REPORTS_DIR


def validate_settings(settings):
    allowed={'title','organization','context','commentary','accent','chart_ids'}
    if set(settings)-allowed: raise ValueError('Unknown report setting.')
    for key,limit in [('title',150),('organization',150),('context',5000),('commentary',20000)]:
        if not isinstance(settings.get(key,''),str) or len(settings.get(key,''))>limit: raise ValueError(f'{key} exceeds {limit} characters.')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',settings.get('accent','#287a65')): raise ValueError('Choose a six-digit hex branding color.')
    ids=settings.get('chart_ids',[])
    if not isinstance(ids,list) or len(ids)>12 or any(not isinstance(i,str) for i in ids): raise ValueError('Select up to twelve charts.')
    return settings


def chart_image(chart, color):
    fig=Figure(figsize=(9,4.5),layout='constrained'); ax=fig.subplots()
    spec=chart.get('figure',chart.get('fig',{}))
    if isinstance(spec,str):
        import json
        spec=json.loads(spec)
    data=spec.get('data',[])
    if not data: raise ValueError('A selected chart has no exportable data.')
    for trace in data:
        kind=trace.get('type','scatter'); x=trace.get('x',[]); y=trace.get('y',[])
        # Plotly's binary ndarray representation must be converted by the caller.
        if isinstance(x,dict) or isinstance(y,dict): raise ValueError('A selected chart uses an unsupported binary representation.')
        name=str(trace.get('name',''))
        if kind=='heatmap':
            z=trace.get('z',[]); image=ax.imshow(z,aspect='auto',cmap='viridis');fig.colorbar(image,ax=ax)
            if x: ax.set_xticks(range(len(x)),x,rotation=45,ha='right')
            if y: ax.set_yticks(range(len(y)),y)
        elif kind=='bar':
            if trace.get('orientation')=='h': ax.barh(y,x,label=name,color=color)
            else: ax.bar(x,y,label=name,color=color,alpha=.8)
        elif kind=='histogram': ax.hist(x,bins=20,color=color,alpha=.8)
        elif kind=='box':
            if y: ax.boxplot(y)
            elif x: ax.boxplot(x,vert=False)
        elif kind in ('scatter','scattergl'):
            if not len(x): x=list(range(len(y)))
            if 'lines' in trace.get('mode','lines'): ax.plot(x,y,label=name)
            else: ax.scatter(x,y,label=name,s=12,alpha=.7)
        elif kind=='pie': ax.pie(trace.get('values',[]),labels=trace.get('labels',[]),autopct='%1.0f%%')
        else: raise ValueError(f'Chart type {kind} cannot be exported. Deselect it or choose another chart.')
    ax.set_title(chart.get('title','Evidence')); ax.tick_params(axis='x',labelrotation=35,labelsize=8)
    ax.grid(alpha=.12); image=io.BytesIO();fig.savefig(image,format='png',dpi=150);image.seek(0)
    return image


def export_reports(project_id, version_id, settings, charts):
    settings=validate_settings(settings); chosen=[c for c in charts if c['id'] in settings.get('chart_ids',[])]
    if len(chosen)!=len(set(settings.get('chart_ids',[]))): raise ValueError('A selected chart is unavailable. Refresh report evidence.')
    rid=str(uuid.uuid4()); folder=REPORTS_DIR/project_id/'custom'/rid;folder.mkdir(parents=True,exist_ok=True)
    title=settings.get('title') or 'Dataset report'; org=settings.get('organization',''); accent=settings.get('accent','#287a65')
    images=[(c,chart_image(c,accent)) for c in chosen]
    styles=getSampleStyleSheet();styles['Title'].textColor=HexColor(accent)
    content=[Paragraph(escape(title),styles['Title']),Paragraph(escape(org),styles['Normal']),Spacer(1,12),
        Paragraph(escape('Dataset version: '+version_id),styles['Normal'])]
    for heading,key in [('Context','context'),('Commentary','commentary')]:
        content.extend([Spacer(1,14),Paragraph(heading,styles['Heading2'])])
        for para in settings.get(key,'').split('\n'):
            if para.strip(): content.append(Paragraph(escape(para),styles['BodyText']))
    for c,img in images: content.extend([PageBreak(),Paragraph(escape(c['title']),styles['Heading2']),Image(img,width=480,height=240)])
    SimpleDocTemplate(str(folder/'report.pdf'),title=title,author=org).build(content)
    presentation=Presentation();presentation.slide_width=Inches(13.333);presentation.slide_height=Inches(7.5)
    def slide(heading,body=''):
        s=presentation.slides.add_slide(presentation.slide_layouts[6])
        box=s.shapes.add_textbox(Inches(.65),Inches(.4),Inches(12),Inches(.9)).text_frame
        box.text=heading;box.paragraphs[0].font.size=Pt(28);box.paragraphs[0].font.color.rgb=RGBColor.from_string(accent[1:])
        if body:
            t=s.shapes.add_textbox(Inches(.75),Inches(1.55),Inches(11.8),Inches(5.4)).text_frame;t.word_wrap=True;t.text=body
            for p in t.paragraphs:p.font.size=Pt(18)
        return s
    slide(title,org+'\nDataset version: '+version_id)
    for heading,key in [('Context','context'),('Commentary','commentary')]:
        text=settings.get(key,'')
        # Bounded chunks keep long user commentary editable and on-slide.
        chunks=[]; chunk=''
        for word in text.split():
            if len(chunk)+len(word)>650:chunks.append(chunk);chunk=''
            chunk+=word+' '
        if chunk:chunks.append(chunk)
        for i,body in enumerate(chunks):slide(heading+(f' · {i+1}' if len(chunks)>1 else ''),body)
    for c,img in images:
        s=slide(c['title']);img.seek(0);s.shapes.add_picture(img,Inches(.65),Inches(1.5),width=Inches(12),height=Inches(6))
    presentation.save(folder/'report.pptx')
    return dict(report_id=rid,version_id=version_id,settings=settings)
