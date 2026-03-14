import traceback
try:
    from modelscope.pipelines import pipeline
except:
    traceback.print_exc()