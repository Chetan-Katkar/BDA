import json, csv, re
D = json.load(open('companies.json'))
NF = lambda v: (not v) or str(v).strip().lower().startswith('not found')

# ---- Removals, grouped by the user's five criteria -------------------------
REMOVE = {
 # 1. duplicate / merged entity
 'DST Worldwide Services India (SS&C group)':
   ('DUPLICATE', 'Part of the SS&C group and listed at the same Mindspace Bldg 5&6 Airoli address as the SS&C Technologies entry - same office, same careers pipeline.'),
 # 2. unverified location (single uncorroborated listing, sector/pincode only, or registered-office only)
 'RI Infotech': ('UNVERIFIED LOCATION', 'Only a sector-level "Sector 11, CBD Belapur" mention on one aggregator search page. No street address, website or corroborating source.'),
 'Parivartan AI': ('UNVERIFIED LOCATION', 'Only a pincode (400708 Airoli). No street address published; could not confirm a physical office.'),
 'Continuum Information Systems': ('UNVERIFIED LOCATION', 'Tenancy at Reliable Tech Park appears in one property tenant listing only. No website, no corroboration, current operating status unconfirmed.'),
 'NetBiz Systems': ('UNVERIFIED LOCATION', 'Appears only in the Vishwaroop IT Park tenant listing. No website, no second source.'),
 'Huawei Telecommunications (India) Co Pvt Ltd': ('UNVERIFIED LOCATION', 'Vashi presence rests on a building tenant listing. Huawei publishes no first-party India office page confirming a Vashi site.'),
 'Payfront Technologies India Pvt Ltd (formerly Excelity Global)': ('UNVERIFIED LOCATION', 'Single tenant-listing source for the Vashi office; no first-party confirmation.'),
 'Ness Digital Engineering (Ness Technologies India)': ('UNVERIFIED LOCATION', 'Single tenant-listing source; no first-party page confirming a current Airoli site after the Ness rebrand.'),
 'Black Box Ltd (Black Box Network Services)': ('UNVERIFIED LOCATION', 'Single Gigaplex tenant-listing source; no corroboration and no contact channel.'),
 'CMA CGM Shared Service Centre India': ('UNVERIFIED LOCATION', 'Single tenant-listing source; also a shipping shared-service centre rather than a software employer.'),
 'AIBiStreet': ('UNVERIFIED LOCATION', 'Address comes from one blog listing. No website, no registry or map corroboration.'),
 'Prosper Technology Solutions': ('UNVERIFIED LOCATION', 'One directory listing only. No website or contact channel to confirm the office exists.'),
 'SLB (Schlumberger) Mahape office': ('UNVERIFIED LOCATION', 'Mahape presence reported only by area guide blogs. No first-party SLB page confirms a Millennium Business Park site.'),
 'Vayutech Global Solutions Pvt Ltd': ('UNVERIFIED LOCATION', 'Only a registered office in a residential flat in Kharghar. No operating office confirmed; also no verifiable email.'),
 'Finicity Technologies Pvt Ltd': ('UNVERIFIED LOCATION', 'Only an MCA-registered address, which is not evidence of an operating office. Post-acquisition status of the India entity is unconfirmed.'),
 'Crisco Consulting': ('UNVERIFIED LOCATION', 'Directory plus tenant listing only; no website or contact confirmed.'),
 'Nestcraft Design Studio': ('UNVERIFIED LOCATION', 'One yellow-pages listing only; no website or corroborating source.'),
 # 3. no meaningful technology / software relevance
 'ICICI Bank (Aurum Q Parc technology/operations office)': ('NOT TECH-RELEVANT', 'A retail bank. No verified software-engineering function at this Ghansoli site, and hiring runs through general bank recruitment.'),
 'Axis Securities Ltd': ('NOT TECH-RELEVANT', 'A broking firm. No verified in-house engineering team at this site.'),
 'Aon India (Aon Services India)': ('NOT TECH-RELEVANT', 'Insurance broking and professional services, not a software or product organisation.'),
 'Arcadis India': ('NOT TECH-RELEVANT', 'Design and engineering consultancy; no verified software-development function at the Navi Mumbai sites.'),
 'Hinduja Global Solutions (HGS)': ('NOT TECH-RELEVANT', 'BPM/process outsourcing. The Vashi intake is process work, not software engineering.'),
 'DP World Global Service Centre': ('NOT TECH-RELEVANT', 'Ports and logistics shared-service centre; the indexed Ghansoli roles are operations, not software.'),
 'FirstRand Services Pvt Ltd (FirstRand Bank India GCC)': ('NOT TECH-RELEVANT', 'Bank captive centre with no verified software-engineering function or recruitment channel.'),
 # 4. listed email guessed or unverifiable
 'e2Serv Ventures Pvt Ltd (e2Serv Technologies)': ('UNVERIFIABLE EMAIL', 'The only contact found was a personal-style yahoo.com address on a B2B directory - not a verifiable company mailbox. Three different registered addresses also made the operating office unclear.'),
}
# (Skypal System and Nipralo were already excluded before the list was built.)

# ---- Email fields downgraded rather than deleting an otherwise-valid company
DOWNGRADE = {
 'FynTune Solution Pvt Ltd': ('gen_email', 'Not found - the only address found was an individual CEO mailbox reported by third parties; not independently verifiable, so removed.'),
 'Azentio Software Pvt Ltd': ('gen_email', 'Not found - legal@azentio.com exists but is a legal mailbox, not a company contact or recruitment channel.'),
}

kept, removed = [], []
for r in D:
    if r['company'] in REMOVE:
        crit, why = REMOVE[r['company']]
        r['_criterion'], r['_why_removed'] = crit, why
        removed.append(r)
    else:
        if r['company'] in DOWNGRADE:
            f, note = DOWNGRADE[r['company']]
            r[f] = note
        kept.append(r)

# ---- Six-point readiness flags -------------------------------------------
def flags(r):
    f = {}
    f['1 HR/recruitment email'] = 'YES' if not NF(r.get('hr_email')) else 'no'
    f['2 General company email'] = 'YES' if not NF(r.get('gen_email')) else 'no'
    f['3 LinkedIn page']         = 'YES' if not NF(r.get('linkedin')) else 'no'
    f['4 Careers page']          = 'YES' if not NF(r.get('careers')) else 'no'
    f['5 Current opening']       = 'YES' if str(r.get('opening','')).strip().upper().startswith('YES') else 'no'
    f['6 Prior intern/fresher evidence'] = 'YES' if not NF(r.get('evidence')) else 'no'
    return f

for r in kept:
    r['_f'] = flags(r)
    r['_ready'] = sum(1 for v in r['_f'].values() if v == 'YES')
    r['_contactable'] = 'YES' if (r['_f']['1 HR/recruitment email']=='YES' or r['_f']['2 General company email']=='YES') else 'no'

kept.sort(key=lambda r: (-(r['_f']['1 HR/recruitment email']=='YES')*10 - r['_ready'], r['company']))
json.dump(kept, open('verified_final.json','w'), indent=1, ensure_ascii=False)
json.dump(removed, open('removed.json','w'), indent=1, ensure_ascii=False)

FK = ['1 HR/recruitment email','2 General company email','3 LinkedIn page','4 Careers page','5 Current opening','6 Prior intern/fresher evidence']
with open('verified_final.csv','w',newline='',encoding='utf-8') as fh:
    w = csv.writer(fh)
    w.writerow(['No.','Company','Area / Address','Nearest Station','Approx. Distance','Company Type','Technology / Domain']
               + FK + ['Score /6','Emailable now','HR Email','General Email','Phone','Website','Careers Page','LinkedIn',
                       'Relevant Roles','Current Opening detail','Internship Evidence detail','Cold outreach practical?','Sources'])
    for i,r in enumerate(kept,1):
        w.writerow([i,r['company'],r['area'],r['station'],r['dist'],r['type'],r['domain']]
                   + [r['_f'][k] for k in FK]
                   + [r['_ready'],r['_contactable'],r.get('hr_email'),r.get('gen_email'),r.get('phone'),
                      r.get('website'),r.get('careers'),r.get('linkedin'),r.get('roles'),
                      r.get('opening'),r.get('evidence'),r.get('cold'),r.get('sources')])
with open('removed.csv','w',newline='',encoding='utf-8') as fh:
    w = csv.writer(fh); w.writerow(['No.','Company','Removal criterion','Reason','Area','Station'])
    for i,r in enumerate(sorted(removed,key=lambda x:(x['_criterion'],x['company'])),1):
        w.writerow([i,r['company'],r['_criterion'],r['_why_removed'],r['area'],r['station']])

from collections import Counter
print('kept:', len(kept), '| removed:', len(removed))
print('removal criteria:', dict(Counter(r['_criterion'] for r in removed)))
print('flag totals:', {k: sum(1 for r in kept if r['_f'][k]=='YES') for k in FK})
print('emailable now:', sum(1 for r in kept if r['_contactable']=='YES'))
print('stations:', dict(Counter(r['station'].split(' /')[0].split(' (')[0].strip() for r in kept)))
