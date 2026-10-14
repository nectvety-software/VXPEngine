import sys
print(sys.executable)
print(sys.version)
try:
    import PIL
    print("PIL", PIL.__file__)
except Exception as e:
    print("ERR", e)
print([p for p in sys.path if p])
