"""Deterministic synthetic business CSVs; no personal customer data."""
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path


def generate(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    rng=random.Random(42)
    retail=[]
    for i in range(600):
        sales=round(rng.uniform(15,900),2)
        profit=round(sales*rng.uniform(-0.15,0.4),2)
        retail.append(dict(order_id=f'ORD-{i+1:05}',order_date=str(date(2025,1,1)+timedelta(days=i%365)),
            region=['East','West','North','South'][i%4],category=['Electronics','Home, office','Apparel'][i%3],
            sales=sales,profit=profit,quantity=i%9+1,customer_note='Montréal café' if i%20==0 else '',
            discount='' if i%17==0 else round(rng.uniform(0,0.3),2)))
    # Returns, missing fields and duplicated transactions occur in actual exports.
    retail.extend([dict(retail[0]),dict(retail[21])])
    retail.append(dict(retail[5],order_id='RETURN-001',sales=-120,profit=-30))
    churn=[]
    for i in range(300):
        tenure=i%48+1;tickets=rng.randrange(8)
        churn.append(dict(customer_id=f'SUB-{i:05}',tenure_months=tenure,tier=['Starter','Pro','Enterprise'][i%3],
            monthly_revenue=[29,99,499][i%3],support_tickets=tickets,churned=int(tickets>4 and tenure<24)))
    for filename,rows in [('retail_orders.csv',retail),('saas_churn.csv',churn)]:
        with (directory/filename).open('w',encoding='utf-8-sig',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    manifest=dict(retail_rows=len(retail),retail_sales_total=round(sum(r['sales'] for r in retail),2),
        retail_profit_total=round(sum(r['profit'] for r in retail),2),churn_rows=len(churn),
        churn_count=sum(r['churned'] for r in churn))
    (directory/'expected.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


if __name__=='__main__':
    generate(Path(__file__).with_name('data'))
