import baostock as bs
bs.login()
for flag in ["2","1","3"]:
    rs=bs.query_history_k_data_plus("sz.300750", "date,open,high,low,close,volume,amount", start_date="2026-11-05", end_date="2026-11-07", frequency="d", adjustflag=flag)
    print(flag, rs.error_code)
    while rs.error_code=="0" and rs.next():
        print(flag, rs.get_row_data())
bs.logout()
