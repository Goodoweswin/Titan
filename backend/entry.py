from titan_wb.engine import main,serve

if __name__ == '__main__':
    import sys
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    if '--if-job' in sys.argv:
        from titan_if.jobs import run
        run(sys.argv[sys.argv.index('--if-job')+1])
    elif '--stdio-server' in sys.argv:serve(sys.stdin.buffer,sys.stdout.buffer)
    else:main()
