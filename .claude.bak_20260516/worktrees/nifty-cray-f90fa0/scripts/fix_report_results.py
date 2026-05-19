"""One-time script to replace the Results section in training-report.tsx."""
import sys

filepath = r'c:\Users\panca\Documents\Github\Agent_Swarm\ui\src\components\training\training-report.tsx'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Replace lines 319-345 (0-indexed 318-344)
old_section = ''.join(lines[318:345])

new_section = '      {/* Results */}\n' \
'      {(isCompleted || (isRunning && liveData)) && (\n' \
'        <Section\n' \
'          icon={<TrendingDown size={14} className="text-[var(--chat-accent)]" />}\n' \
'          title={isRunning ? "Current Results" : "Results"}\n' \
'        >\n' \
'          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">\n' \
'            <Stat\n' \
'              label="Final Loss"\n' \
'              value={\n' \
'                (isRunning && liveData?.loss != null) ? liveData.loss.toFixed(4)\n' \
'                : r.final_loss != null ? r.final_loss.toFixed(4) : "\u2014"\n' \
'              }\n' \
'            />\n' \
'            <Stat\n' \
'              label="Samples/sec"\n' \
'              value={r.train_samples_per_second ? r.train_samples_per_second.toFixed(2) : "\u2014"}\n' \
'            />\n' \
'            <Stat\n' \
'              label="Steps/sec"\n' \
'              value={r.train_steps_per_second ? r.train_steps_per_second.toFixed(2) : "\u2014"}\n' \
'            />\n' \
'            <Stat\n' \
'              label="Adapter"\n' \
'              value={r.adapter_path ? r.adapter_path.split("/").pop() ?? "\u2014" : isRunning ? "In progress" : "\u2014"}\n' \
'              detail={r.adapter_path ?? undefined}\n' \
'            />\n' \
'          </div>\n' \
'        </Section>\n' \
'      )}\n'

content = ''.join(lines)
if old_section in content:
    content = content.replace(old_section, new_section)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Done - replaced Results section")
else:
    print("ERROR: Could not find old section", file=sys.stderr)
    print(f"Old section repr: {repr(old_section[:100])}", file=sys.stderr)
    sys.exit(1)
