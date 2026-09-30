import sys, json, csv; sys.path.insert(0,'.')
from new_mumbai import N
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

DROP = {"IBM India","Capgemini (Mindspace Malad)","Accenture (Mindspace Malad)","L&T Infotech (LTIMindtree Mumbai)"}
NEW = [n for n in N if n[0] not in DROP]
OLD = json.load(open('companies.json'))
KEPT = {r['company'] for r in json.load(open('verified_final.json'))}
NF = lambda v: (not v) or str(v).strip().lower().startswith('not found')

HDR=PatternFill('solid',fgColor='1F3864'); HF=Font(bold=True,color='FFFFFF',size=9)
THIN=Border(*[Side(style='thin',color='D9D9D9')]*4)
def style(ws,hrow,ncol,widths):
    for ci,w in enumerate(widths,1):
        ws.column_dimensions[get_column_letter(ci)].width=w
        c=ws.cell(hrow,ci); c.fill=HDR; c.font=HF
        c.alignment=Alignment(wrap_text=True,vertical='center',horizontal='center')
    ws.row_dimensions[hrow].height=34
    for row in ws.iter_rows(min_row=hrow+1,max_row=ws.max_row,max_col=ncol):
        for c in row:
            c.alignment=Alignment(vertical='top',wrap_text=True); c.border=THIN; c.font=Font(size=9)

wb=Workbook()

# --- READ ME
rm=wb.active; rm.title='READ ME'
L=[("Mumbai + Navi Mumbai internship target list",14,True),
("Compiled 30 September 2026. For a 2-6 month software / technology internship.",10,False),("",10,False),
("TOTAL: %d companies  =  100 Navi Mumbai (deeply researched)  +  %d wider Mumbai (discovery-level)"%(100+len(NEW),len(NEW)),11,True),
("",10,False),
("READ THIS BEFORE YOU USE THE WIDER MUMBAI SHEET",12,True),
("The two halves of this file are NOT researched to the same depth, and you should treat them differently.",10,False),
("",10,False),
("Navi Mumbai 100 - each row had its address, contacts, careers page and internship evidence",10,False),
("  chased individually. 75 of the 100 passed a strict audit; the other 25 are marked FAILED AUDIT",10,False),
("  with the reason. 21 have a publicly verified email. Use this sheet for actual outreach.",10,False),
("",10,False),
("Wider Mumbai %d - DISCOVERY LEVEL ONLY. Each row is a real company named in a curated industry"%len(NEW),10,False),
("  list, review directory or job listing, with its sector and the source. What it does NOT have:",10,False),
("  verified street address, verified email, verified phone, or verified internship status.",10,False),
("  Confidence MED = a locality or a curated/reviewed directory entry was found. LOW = named in a",10,False),
("  list with no locality. Every one of these needs you to open the company site before contacting.",10,False),
("",10,False),
("WHAT I COULD NOT DO, AND WHY",12,True),
("1. 'Great reviews' could not be verified. Page fetching is blocked in the research environment,",10,False),
("   so Glassdoor / AmbitionBox rating pages could not be opened. Where a directory rating did",10,False),
("   surface in a search result it is written into the Notes column verbatim; otherwise it is absent.",10,False),
("   There is no invented rating anywhere in this file.",10,False),
("2. 'Great stipend' likewise. Stipends appear only where a real listing stated one - for example",10,False),
("   Silicon Interfaces (Rs 15,000-25,000/month) and Host360 (up to Rs 12,000/month).",10,False),
("3. 'Easy to crack' is not something evidence can establish. The closest honest proxy is company",10,False),
("   size plus a live intern posting, so use the Navi Mumbai sheet's priority scoring for that.",10,False),
("4. The target was 250 new companies. I reached %d distinct new ones without padding the list with"%len(NEW),10,False),
("   duplicates, non-technology firms or companies whose Mumbai presence I could not source.",10,False),
("",10,False),
("A NOTE ON WHAT 'EASY' ACTUALLY LOOKS LIKE",12,True),
("Easy to crack, great stipend and great reviews rarely occur together. Dream11, BrowserStack,",10,False),
("Google and the bank GCCs pay best and review well - and are the hardest to enter. The small",10,False),
("Navi Mumbai firms with a published hr@ mailbox are the ones most likely to write back.",10,False),
("Realistic plan: apply to the big names through their portals, and cold-email the small ones.",10,False),
("",10,False),
("SHEETS",12,True),
("All Companies - everything in one sortable table.",10,False),
("Navi Mumbai 100 - full detail incl. audit status and the six-point readiness check.",10,False),
("Wider Mumbai %d - the new discovery pool."%len(NEW),10,False),
("Emailable Now - the 21 with a publicly verified email address. Start here.",10,False)]
for i,(t,s,b) in enumerate(L,1):
    c=rm.cell(i,1,t); c.font=Font(size=s,bold=b)
rm.column_dimensions['A'].width=118

# --- All Companies
ws=wb.create_sheet('All Companies')
cols=['No.','Company','Source list','Area / Office','Zone / Nearest Station','Sector / Technology','Status',
      'HR Email','General Email','Phone','Website','Careers Page','Confidence','Notes','Source']
ws.append(cols); n=0
for r in OLD:
    n+=1
    st='AUDIT PASSED' if r['company'] in KEPT else 'FAILED AUDIT - see Navi Mumbai sheet'
    ws.append([n,r['company'],'Navi Mumbai 100',r['area'],r['station'],r['domain'],st,
               r.get('hr_email'),r.get('gen_email'),r.get('phone'),r.get('website'),r.get('careers'),
               'HIGH - individually researched',r.get('opening'),str(r.get('sources'))[:150]])
for nm,area,zone,sector,conf,src in NEW:
    n+=1
    ws.append([n,nm,'Wider Mumbai','Not found - verify on company site',zone,sector,'DISCOVERY ONLY',
               'Not found','Not found','Not found','Not found','Not found',
               conf+' - discovery level',area,src])
style(ws,1,len(cols),[5,34,15,34,22,38,26,26,26,18,26,30,26,30,34])
ws.freeze_panes='C2'; ws.auto_filter.ref=ws.dimensions

# --- Navi Mumbai 100
ws2=wb.create_sheet('Navi Mumbai 100')
d=[('No.',None,5),('Company','company',32),('Audit','_audit',30),('Area / Address','area',42),
   ('Nearest Station','station',16),('Approx Distance','dist',20),('Type','type',24),('Technology / Domain','domain',36),
   ('Relevant Roles','roles',36),('Current Opening?','opening',28),('Internship Evidence','evidence',42),
   ('HR Email','hr_email',26),('General Email','gen_email',26),('Phone','phone',18),('Website','website',26),
   ('Careers Page','careers',32),('LinkedIn','linkedin',28),('Size','size',16),('Cold Outreach?','cold',40),('Sources','sources',60)]
ws2.append([c[0] for c in d])
for i,r in enumerate(OLD,1):
    r['_audit']='PASSED' if r['company'] in KEPT else 'FAILED AUDIT'
    ws2.append([i]+[r.get(c[1],'Not found') for c in d[1:]])
style(ws2,1,len(d),[c[2] for c in d]); ws2.freeze_panes='C2'; ws2.auto_filter.ref=ws2.dimensions

# --- Wider Mumbai
ws3=wb.create_sheet('Wider Mumbai %d'%len(NEW))
ws3['A1']=('DISCOVERY LEVEL. Real companies, real sources, but address / email / phone / internship status are NOT verified. '
           'Open the company site before contacting. Confidence MED = locality or reviewed-directory entry found; LOW = named in a list only.')
ws3.merge_cells('A1:G1'); ws3['A1'].font=Font(bold=True,size=10)
ws3['A1'].alignment=Alignment(wrap_text=True,vertical='center'); ws3.row_dimensions[1].height=30
ws3.append(['No.','Company','Locality / detail found','Zone','Sector / Technology','Confidence','Source'])
for i,(nm,area,zone,sector,conf,src) in enumerate(NEW,1):
    ws3.append([i,nm,area,zone,sector,conf,src])
style(ws3,2,7,[5,38,44,24,44,14,38]); ws3.freeze_panes='A3'; ws3.auto_filter.ref='A2:G%d'%ws3.max_row

# --- Emailable
ws4=wb.create_sheet('Emailable Now')
em=[r for r in OLD if r['company'] in KEPT and (not NF(r.get('hr_email')) or not NF(r.get('gen_email')))]
em.sort(key=lambda r: NF(r.get('hr_email')))
ws4['A1']='The 21 audited companies with a publicly verified email. HR mailboxes first. None of these was guessed or built from a naming pattern.'
ws4.merge_cells('A1:G1'); ws4['A1'].font=Font(bold=True,size=10)
ws4['A1'].alignment=Alignment(wrap_text=True,vertical='center'); ws4.row_dimensions[1].height=26
ws4.append(['No.','Company','Station','HR Email','General Email','Phone','Mailbox type'])
for i,r in enumerate(em,1):
    ws4.append([i,r['company'],r['station'],r.get('hr_email'),r.get('gen_email'),r.get('phone'),
                'HR / recruitment' if not NF(r.get('hr_email')) else 'General / business'])
style(ws4,2,7,[5,36,20,32,32,20,20]); ws4.freeze_panes='A3'

wb.save('Mumbai_NaviMumbai_Internship_Master.xlsx')

with open('all_companies_combined.csv','w',newline='',encoding='utf-8') as f:
    w=csv.writer(f); w.writerow(cols); n=0
    for r in OLD:
        n+=1; st='AUDIT PASSED' if r['company'] in KEPT else 'FAILED AUDIT'
        w.writerow([n,r['company'],'Navi Mumbai 100',r['area'],r['station'],r['domain'],st,r.get('hr_email'),
                    r.get('gen_email'),r.get('phone'),r.get('website'),r.get('careers'),'HIGH',r.get('opening'),r.get('sources')])
    for nm,area,zone,sector,conf,src in NEW:
        n+=1
        w.writerow([n,nm,'Wider Mumbai','Not found',zone,sector,'DISCOVERY ONLY','Not found','Not found',
                    'Not found','Not found','Not found',conf,area,src])
import os
print('total rows:',100+len(NEW),'| new:',len(NEW))
print('xlsx bytes:',os.path.getsize('Mumbai_NaviMumbai_Internship_Master.xlsx'))
