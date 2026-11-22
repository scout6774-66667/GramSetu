import zipfile
import csv
import io
import hashlib
import os
from pipeline import FIELDS, read_normalized, audit_v2_2_zip

def prepare_baseline():
    os.makedirs('contracts', exist_ok=True)
    with zipfile.ZipFile('GramSetu_All_Corrected_CSV_v2_2.zip', 'r') as z:
        raw_bytes = z.read('csv/market_prices.csv')
        raw_sha = hashlib.sha256(raw_bytes).hexdigest()
        reader = csv.DictReader(io.StringIO(raw_bytes.decode('utf-8')))
        rows = list(reader)

    norm_rows = []
    for r in rows:
        obs_id = r['price_observation_id']
        mkt = r['market_id']
        cmd = r['commodity_id']
        var = r['variety'].strip() or 'NOT_REPORTED'
        grd = r['grade'].strip() or 'NOT_REPORTED'
        obs_date = r['observed_date']
        min_p = r['min_price_inr_quintal']
        mod_p = r['modal_price_inr_quintal']
        max_p = r['max_price_inr_quintal']
        src_id = r.get('source_id', 'SRC_REPUBLISHED_AGMARKNET_1')
        src_key = f"{src_id}|{mkt}|{cmd}|{obs_date}"
        src_url = r.get('source_url') or 'https://data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi'
        retrieved = f"{r.get('retrieval_date', '2026-11-18')}T06:00:00+00:00"
        tier = 'SECONDARY_REPUBLISHED'
        sim_flag = 'False'
        rev_status = 'NOT_REVIEWED'
        rev_id = 'NOT_REVIEWED'
        norm_rows.append({
            'observation_id': obs_id,
            'market_id': mkt,
            'commodity_id': cmd,
            'variety': var,
            'grade': grd,
            'observed_date': obs_date,
            'min_price_inr_quintal': min_p,
            'modal_price_inr_quintal': mod_p,
            'max_price_inr_quintal': max_p,
            'source_record_key': src_key,
            'source_url': src_url,
            'source_file_sha256': raw_sha,
            'retrieved_at_utc': retrieved,
            'source_tier': tier,
            'simulation_flag': sim_flag,
            'review_status': rev_status,
            'review_id': rev_id
        })

    norm_path = 'contracts/market_prices_normalized.csv'
    with open(norm_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(norm_rows)

    print(f'Wrote {norm_path} with {len(norm_rows)} rows.')
    validated = read_normalized(norm_path)
    print(f'Validated successfully! Count = {len(validated)}')

    audit = audit_v2_2_zip('GramSetu_All_Corrected_CSV_v2_2.zip')
    print('audit_v2_2_zip result:', audit)

if __name__ == '__main__':
    prepare_baseline()
