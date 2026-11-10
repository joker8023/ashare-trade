import baostock as bs
lg = bs.login()
print("login", lg.error_code, lg.error_msg)
for code in ["sh.603838", "sz.002951"]:
    rs = bs.query_history_k_data_plus(code, "date,time,code,open,high,low,close,volume,amount", start_date="2024-01-01", end_date="2024-02-29", frequency="60", adjustflag="2")
    print(code, "err", rs.error_code, rs.error_msg)
    rows = []
    while rs.next():
        rows.append(rs.get_row_data())
    print(code, "bars jan-feb2024:", len(rows))
    print(rows[:2])
    print(rows[-2:] if rows else [])
bs.logout()
print("DONE")
