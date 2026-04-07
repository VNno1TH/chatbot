import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('tests/evaluation_results.json', encoding='utf-8') as f:
    data = json.load(f)

print('=== SUMMARY ===')
for k, v in data['summary'].items():
    print(f'  {k}: {v}')

print('\n=== LOW SCORING (RAGAS < 3.0) ===')
low = [r for r in data['results'] if r['ragas_score'] < 3.0]
for r in low:
    ic = 'Y' if r['intent_correct'] else 'N'
    print(f"  {r['id']:12s} RAGAS:{r['ragas_score']:.2f} I:{r['expected_intent']}/{r['predicted_intent']}({ic}) Fact:{r['factual_accuracy']:.0%} Faith:{r['faithfulness']} Comp:{r['completeness']}")
    print(f"    Q: {r['question'][:70]}")
    a = r['answer'][:100].replace('\n', ' ')
    print(f"    A: {a}")
    print(f"    GT: {r['ground_truth_full'][:100]}")
    print()

print(f'Total low-scoring: {len(low)}/{len(data["results"])}')

print('\n=== INTENT ERRORS ===')
for r in data['results']:
    if not r['intent_correct']:
        print(f"  {r['id']:12s} Exp:{r['expected_intent']} Got:{r['predicted_intent']} Q: {r['question'][:60]}")

print('\n=== MEDIUM SCORING (3.0-3.5) ===')
mid = [r for r in data['results'] if 3.0 <= r['ragas_score'] < 3.5]
for r in mid:
    print(f"  {r['id']:12s} RAGAS:{r['ragas_score']:.2f} Fact:{r['factual_accuracy']:.0%} Q: {r['question'][:60]}")
print(f'Total medium: {len(mid)}')
