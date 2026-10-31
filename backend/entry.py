from titan_wb.engine import main,serve

if __name__ == '__main__':
    import sys
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    if '--stdio-server' in sys.argv:serve(sys.stdin.buffer,sys.stdout.buffer)
    else:main()
