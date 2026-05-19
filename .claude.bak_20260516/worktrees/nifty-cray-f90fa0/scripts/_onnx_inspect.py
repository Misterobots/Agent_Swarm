import onnx
import json, os

model_path = '/home/misterobots/bmo_client/hey_beeMo.onnx'
m = onnx.load(model_path)

print("=== ONNX Model Metadata ===")
print(f"IR version: {m.ir_version}")
print(f"Opset: {[op.version for op in m.opset_import]}")
print(f"Doc string: {m.doc_string!r}")
print(f"Model version: {m.model_version}")

print("\n=== Custom metadata_props ===")
for prop in m.metadata_props:
    print(f"  {prop.key}: {prop.value}")

print("\n=== Input shapes ===")
for inp in m.graph.input:
    print(f"  {inp.name}: {inp.type}")

print("\n=== Output shapes ===")
for out in m.graph.output:
    print(f"  {out.name}: {out.type}")
