try:
    with open('/tmp/flows.txt', 'r') as f:
        for line in f:
            if 'explicit' in line:
                print(line.split('::')[1].strip())
except Exception as e:
    print(e)
