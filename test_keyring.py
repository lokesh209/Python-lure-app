import keyring
try:
    keyring.set_password("test_svc", "test_usr", "test_pass")
    print("SET OK")
    print("GET:", keyring.get_password("test_svc", "test_usr"))
except Exception as e:
    print("ERROR:", e)
