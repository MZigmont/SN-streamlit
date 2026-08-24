# FOR FUTURE CONSIDERATION:  BACKLOG




8/17/2026 - fix email sending bug
ValueError: could not convert string to float: '1,000.00'
Traceback:
File "C:\Users\mzigm\AppData\Local\Programs\Python\Python312\Lib\site-packages\streamlit\runtime\scriptrunner\exec_code.py", line 88, in exec_func_with_error_handling
    result = func()
             ^^^^^^
File "C:\Users\mzigm\AppData\Local\Programs\Python\Python312\Lib\site-packages\streamlit\runtime\scriptrunner\script_runner.py", line 579, in code_to_exec
    exec(code, module.__dict__)
File "C:\Users\mzigm\OneDrive\Desktop\sn_streamlit\pages\send_emails.py", line 513, in <module>
    main()
File "C:\Users\mzigm\OneDrive\Desktop\sn_streamlit\pages\send_emails.py", line 491, in main
    payload = _template_payload(row, start_date, end_date)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "C:\Users\mzigm\OneDrive\Desktop\sn_streamlit\pages\send_emails.py", line 135, in _template_payload
    "last_donation_amount": _money(row.get("last_donation_amount")),
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "C:\Users\mzigm\OneDrive\Desktop\sn_streamlit\pages\send_emails.py", line 84, in _money
    return f"${float(value):,.2f}"
               ^^^^^^^^^^^^