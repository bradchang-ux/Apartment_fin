# -*- coding: utf-8 -*-
"""clean_bank_tx module for backend use"""

import pandas as pd
import re
import os
import docx
from io import StringIO
import json

def process_bank_transactions(input_filepath, virtual_filepath=None):
    """
    Reads bank export details and translates them into double-entry bookkeeping format.
    Returns the cleaned data as a list of dictionaries (JSON-ready).
    """
    try:
        if input_filepath.lower().endswith('.docx'):
            doc = docx.Document(input_filepath)
            html_text = '\n'.join([p.text for p in doc.paragraphs])
            dfs = pd.read_html(StringIO(html_text))
            df_raw = dfs[0]
        else:
            dfs = pd.read_html(input_filepath)
            df_raw = dfs[0]

        headers = df_raw.iloc[0].tolist()
        df = df_raw[1:].copy()
        df.columns = headers
    except Exception as e:
        print(f"Failed handling HTML/DOCX: {e}, falling back to CSV")
        df = pd.read_csv(input_filepath)

    mapping = {}  # key: first6+last2 digits of account number -> unit code
    if virtual_filepath and os.path.exists(virtual_filepath):
        try:
            v_df = pd.read_excel(virtual_filepath, header=1)
            for _, v_row in v_df.iterrows():
                acc = str(v_row.get('帳號', '')).strip().lstrip('0')
                code = str(v_row.get('代號', '')).strip()
                if acc and acc.lower() != 'nan' and len(acc) >= 8:
                    key = acc[:6] + acc[-2:]  # 前6位+後2位
                    mapping[key] = code
        except Exception as e:
            print(f"Virtual mapping file error: {e}")

    cleaned_data = []

    for _, row in df.iterrows():
        date_str = str(row.get('帳務日期', '')).strip()
        if len(date_str) == 8 and date_str.isdigit():
            date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        else:
            continue

        withdrawal = str(row.get('提出金額', '')).replace(',', '').replace('.00', '').strip()
        deposit = str(row.get('存入金額', '')).replace(',', '').replace('.00', '').strip()
        balance = str(row.get('餘額', '')).replace(',', '').replace('.00', '').strip()

        remarks = str(row.get('備註', '')).strip()
        remarks = "" if remarks.lower() == 'nan' else remarks

        virt_acc = str(row.get('虛擬帳號', '')).replace('.0', '').strip()
        virt_acc = "" if virt_acc.lower() in ['nan', '0'] else virt_acc

        income = int(float(deposit)) if deposit and deposit.lower() != 'nan' and float(deposit) > 0 else ""
        expense = int(float(withdrawal)) if withdrawal and withdrawal.lower() != 'nan' and float(withdrawal) > 0 else ""

        if not income and not expense:
            continue

        balance_val = int(float(balance)) if balance and balance.lower() != 'nan' else 0

        fmt_income = f"{income:,}" if income != "" else ""
        fmt_expense = f"{expense:,}" if expense != "" else ""
        fmt_balance = f"{balance_val:,}"

        code = ""
        virt_stripped = virt_acc.lstrip('0')
        
        # Match by first 6 + last 2 digits of virtual account
        if virt_stripped and len(virt_stripped) >= 8:
            virt_key = virt_stripped[:6] + virt_stripped[-2:]
            if virt_key in mapping:
                code = mapping[virt_key]
        
        # If no match, try extracting account numbers from remarks (備註)
        if not code and remarks:
            acc_matches = re.findall(r'\d{10,16}', remarks)
            for acc_match in acc_matches:
                acc_clean = acc_match.lstrip('0')
                if len(acc_clean) >= 8:
                    rem_key = acc_clean[:6] + acc_clean[-2:]
                    if rem_key in mapping:
                        code = mapping[rem_key]
                        break

        category = "管理費收入" if code else ""
        if '蓮園心悅大廈管理委員' in remarks:
            category = '利息收入'
            code = '定存轉息'
        elif '27939741' in remarks:
            category = '電信費'
            code = '網路與電話費'
        elif '16432004085' in remarks:
            category = '台電'
            code = '電信室電費'

        cleaned_data.append({
            'date': date,
            'category': category,
            'code': code,
            'income': fmt_income,
            'expense': fmt_expense,
            'balance': fmt_balance,
            'remarks': remarks,
            'virtualAccount': virt_acc
        })

    return cleaned_data