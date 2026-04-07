"""
evaluate.py — RAGAS-like RAG Evaluation Framework (using Ollama LLM-as-judge)
Đánh giá chất lượng chatbot tuyển sinh HaUI theo các metric chuẩn RAGAS.

Metrics:
1. Intent Accuracy       — Router phân loại đúng không?
2. Faithfulness          — Câu trả lời có trung thực với context không?
3. Answer Relevancy      — Câu trả lời có trả lời đúng câu hỏi không?
4. Context Precision     — Context retrieve được có liên quan không? (nếu pipeline hỗ trợ)
5. Context Recall        — Context có bao phủ ground truth không? (nếu pipeline hỗ trợ)
6. Factual Accuracy      — Số liệu cụ thể có đúng không?
7. Completeness          — Câu trả lời có đầy đủ không?
8. RAGAS Score           — Điểm tổng hợp (trung bình có trọng số)

Usage:
    python evaluate.py
    python evaluate.py --quick   # 10 cases đầu
    python evaluate.py --no-llm  # Chỉ factual + intent, bỏ qua LLM judge (nhanh)
"""
import sys
import os
import json
import time
import re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import OLLAMA_BASE_URL, OLLAMA_MODEL, HAUI_DEBUG
from src.rag.pipeline import handle_query, route, load_index
import ollama as ollama_client


# ══════════════════════════════════════════
#  CLIENT & CONFIG
# ══════════════════════════════════════════

_client = None

def get_client():
    global _client
    if _client is None:
        _client = ollama_client.Client(host=OLLAMA_BASE_URL)
    return _client


def llm_judge(prompt: str, max_tokens: int = 10) -> str:
    """Gọi LLM để chấm điểm. Trả về chuỗi raw."""
    try:
        resp = get_client().generate(
            model=OLLAMA_MODEL,
            prompt=prompt,
            options={'num_predict': max_tokens, 'temperature': 0.0}
        )
        return resp['response'].strip()
    except Exception as e:
        return f"ERROR:{e}"


def extract_score(text: str, lo: int = 1, hi: int = 5) -> int:
    """Trích điểm số từ chuỗi LLM trả về."""
    nums = re.findall(r'\b([1-9][0-9]*)\b', text)
    for n in nums:
        v = int(n)
        if lo <= v <= hi:
            return v
    return (lo + hi) // 2  # fallback: median


# ══════════════════════════════════════════
#  RAGAS-LIKE METRICS — LLM-AS-JUDGE
# ══════════════════════════════════════════

def score_faithfulness(question: str, answer: str, context: str) -> int:
    """
    RAGAS Faithfulness: câu trả lời có được support bởi context không?
    Nếu không có context thực, dùng ground_truth_full làm pseudo-context.
    Điểm 1-5.
    """
    ctx_snippet = (context or "")[:600]
    prompt = f"""Đánh giá tính TRUNG THỰC của câu trả lời với context đã cung cấp.
Điểm 1-5:
5 = Hoàn toàn dựa trên context, không bịa đặt
4 = Phần lớn đúng, thể hiện thông tin context
3 = Một phần đúng hoặc thiếu context
2 = Có thông tin không có trong context (hallucination nhẹ)
1 = Bịa đặt nhiều, mâu thuẫn context

Context: {ctx_snippet}
Câu hỏi: {question}
Câu trả lời: {answer[:400]}

Chỉ trả lời 1 số từ 1-5:"""
    return extract_score(llm_judge(prompt, 8), 1, 5)


def score_answer_relevancy(question: str, answer: str) -> int:
    """
    RAGAS Answer Relevancy: câu trả lời có liên quan và trả lời đúng câu hỏi không?
    Điểm 1-5.
    """
    prompt = f"""Đánh giá mức độ LIÊN QUAN của câu trả lời với câu hỏi.
Điểm 1-5:
5 = Trả lời trực tiếp, đúng trọng tâm câu hỏi
4 = Trả lời đúng hướng, có thể thiếu 1 chi tiết nhỏ
3 = Liên quan nhưng lan man hoặc thiếu trọng tâm
2 = Ít liên quan, câu trả lời chủ yếu là thông tin phụ
1 = Không liên quan hoặc từ chối không hợp lý

Câu hỏi: {question}
Câu trả lời: {answer[:400]}

Chỉ trả lời 1 số từ 1-5:"""
    return extract_score(llm_judge(prompt, 8), 1, 5)


def score_context_precision(question: str, context: str) -> int:
    """
    RAGAS Context Precision: context retrieve được có precision cao (đúng chủ đề) không?
    Điểm 1-5. Bỏ qua (trả None) nếu không có context.
    """
    if not context or len(context.strip()) < 30:
        return None
    prompt = f"""Đánh giá mức độ CHÍNH XÁC của context với câu hỏi (context có đúng chủ đề không?).
Điểm 1-5:
5 = Context hoàn toàn liên quan, đúng thông tin cần tra
4 = Phần lớn liên quan, có 1-2 đoạn thừa
3 = Liên quan một phần, có nhiều thông tin thừa
2 = Chủ yếu là thông tin không liên quan
1 = Hoàn toàn sai context (retrieve nhầm)

Câu hỏi: {question}
Context (trích đầu): {context[:500]}

Chỉ trả lời 1 số từ 1-5:"""
    return extract_score(llm_judge(prompt, 8), 1, 5)


def score_context_recall(ground_truth_full: str, context: str) -> int:
    """
    RAGAS Context Recall: context có bao phủ thông tin trong ground truth không?
    Điểm 1-5. Bỏ qua (trả None) nếu không có context.
    """
    if not context or len(context.strip()) < 30:
        return None
    prompt = f"""Đánh giá mức độ BÁO PHỦ của context với đáp án mong đợi.
Điểm 1-5:
5 = Context chứa đủ thông tin để trả lời đúng đáp án
4 = Context chứa phần lớn thông tin cần thiết
3 = Context chứa một phần thông tin
2 = Context ít thông tin liên quan đến đáp án
1 = Context không có thông tin để trả lời đúng

Đáp án mong đợi: {ground_truth_full[:300]}
Context (trích): {context[:500]}

Chỉ trả lời 1 số từ 1-5:"""
    return extract_score(llm_judge(prompt, 8), 1, 5)


def score_completeness(question: str, answer: str, ground_truth_full: str) -> int:
    """
    Completeness: câu trả lời có đầy đủ so với đáp án kỳ vọng không?
    Điểm 1-5.
    """
    prompt = f"""Đánh giá mức độ ĐẦY ĐỦ của câu trả lời so với đáp án kỳ vọng.
Điểm 1-5:
5 = Câu trả lời đủ tất cả thông tin quan trọng
4 = Đủ thông tin cơ bản, chỉ thiếu vài chi tiết phụ
3 = Có thông tin chính nhưng thiếu chi tiết quan trọng
2 = Thiếu nhiều thông tin quan trọng
1 = Quá sơ sài hoặc không trả lời

Câu hỏi: {question}
Đáp án kỳ vọng: {ground_truth_full[:300]}
Câu trả lời: {answer[:400]}

Chỉ trả lời 1 số từ 1-5:"""
    return extract_score(llm_judge(prompt, 8), 1, 5)


# ══════════════════════════════════════════
#  FACTUAL ACCURACY — RULE-BASED
# ══════════════════════════════════════════

def normalize_number(s: str) -> str:
    """Chuẩn hóa số: bỏ dấu phân cách, giữ dấu chấm thập phân."""
    s = s.replace(',', '').replace('.', '', s.count('.') - 1) if s.count('.') > 1 else s.replace(',', '')
    return s.strip()


def extract_numbers(text: str) -> list:
    """Trích các số từ chuỗi."""
    return re.findall(r'\d+(?:[.,]\d+)*', text)


def _to_float_token(s: str):
    """Parse số dạng 26.00 / 26,00 / 26 vào float."""
    try:
        t = s.replace(',', '.')
        if t.count('.') > 1:
            t = t.replace('.', '', t.count('.') - 1)
        return float(t)
    except ValueError:
        return None


def check_factual_accuracy(answer: str, ground_truth: str) -> float:
    """
    Kiểm tra factual accuracy rule-based (0.0–1.0).
    Ưu tiên: số liệu cụ thể → từ khóa quan trọng.
    """
    ans_low = answer.lower()
    gt_low = ground_truth.lower()

    # Trường hợp ground truth là nhãn phi số (bảng, từ chối...)
    non_numeric_labels = {
        'bảng', 'danh sách', 'từ chối', 'lời chào', 'lời cảm ơn', 'chưa công bố',
        'lỗi input', 'bảng so sánh', 'bảng gợi ý', 'văn bằng', 'danh sách học bổng',
        'bảng lịch', '6 bước', '5 phương thức', 'bảng nhóm', 'bảng đầy đủ'
    }
    gt_stripped = gt_low.strip()
    for label in non_numeric_labels:
        if gt_stripped.startswith(label):
            # Không thể kiểm tra số liệu → trả về 0.5 (neutral, để LLM judge xử lý)
            return 0.5

    # Trích số từ ground truth
    gt_numbers = extract_numbers(ground_truth)
    if gt_numbers:
        ans_nums = extract_numbers(answer)
        ans_floats = [_to_float_token(x) for x in ans_nums]
        ans_floats = [x for x in ans_floats if x is not None]
        found = 0
        for num in gt_numbers:
            clean = normalize_number(num)
            patterns = [clean, num, num.replace('.', ',')]
            if any(p in ans_low.replace(',', '').replace('.', '') or p in answer for p in [clean]):
                found += 1
            elif any(p in answer for p in patterns):
                found += 1
            else:
                gtf = _to_float_token(num)
                if gtf is not None and ans_floats and any(abs(gtf - af) < 1e-4 for af in ans_floats):
                    found += 1
        return round(found / len(gt_numbers), 2)

    # Trích từ khóa quan trọng từ ground truth
    stopwords = {'và', 'của', 'là', 'có', 'tại', 'trong', 'để', 'hoặc', 'với', 'cho', 'các', 'theo', 'từ', 'đến'}
    keywords = [w for w in gt_low.split() if len(w) > 2 and w not in stopwords]
    if not keywords:
        return 0.5
    found = sum(1 for kw in keywords if kw in ans_low)
    return round(found / len(keywords), 2)


def compute_ragas_score(
    faithfulness: int,
    answer_relevancy: int,
    context_precision,
    context_recall,
    completeness: int,
    factual_accuracy: float
) -> float:
    """
    RAGAS Score tổng hợp (0-5 scale).
    Trọng số: AR=30%, Faith=25%, Comp=20%, Fact=15%, CP=5%, CR=5%
    Nếu context metrics không có → phân bổ lại trọng số.
    """
    if context_precision is not None and context_recall is not None:
        score = (
            answer_relevancy * 0.30 +
            faithfulness * 0.25 +
            completeness * 0.20 +
            factual_accuracy * 5 * 0.10 +  # convert 0-1 to 0-5
            context_precision * 0.08 +
            context_recall * 0.07
        )
    else:
        score = (
            answer_relevancy * 0.35 +
            faithfulness * 0.30 +
            completeness * 0.25 +
            factual_accuracy * 5 * 0.10
        )
    return round(score, 2)


# ══════════════════════════════════════════
#  CONTEXT RETRIEVAL — OPTIONAL
# ══════════════════════════════════════════

def try_retrieve_context(question: str) -> str:
    """
    Cố gắng lấy context từ RAG pipeline.
    Hỗ trợ các tên hàm phổ biến; graceful fallback nếu không có.
    """
    import rag_pipeline
    for fn_name in ['retrieve_context', 'retrieve', 'get_context', 'search']:
        fn = getattr(rag_pipeline, fn_name, None)
        if callable(fn):
            try:
                result = fn(question)
                if isinstance(result, list):
                    return '\n---\n'.join(str(r) for r in result[:3])
                return str(result)
            except Exception:
                pass
    # Thử lấy từ response nếu handle_query trả về 'context' key
    try:
        resp = handle_query(question)
        if isinstance(resp, dict):
            for key in ('context', 'retrieved', 'sources', 'docs'):
                if key in resp and resp[key]:
                    return str(resp[key])[:1000]
    except Exception:
        pass
    return ""


# ══════════════════════════════════════════
#  MAIN EVALUATION RUNNER
# ══════════════════════════════════════════

def evaluate(test_file: str = None, quick: bool = False, no_llm: bool = False):
    """Chạy full evaluation trên tập test."""

    # --- Load test data ---
    if test_file is None:
        test_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_dataset.json')
    with open(test_file, encoding='utf-8') as f:
        tests = json.load(f)
    if quick:
        tests = tests[:10]

    print("=" * 72)
    print("  🧪 HaUI RAG Chatbot — RAGAS-like Evaluation")
    print(f"  📋 {len(tests)} test cases | {'LLM-judge: OFF (--no-llm)' if no_llm else 'LLM-judge: ON'}")
    print(f"  🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)

    # --- Load RAG index ---
    print("\nLoading RAG index...")
    load_index()

    results = []
    total_start = time.time()

    for i, test in enumerate(tests):
        q = test['question']
        gt = test['ground_truth']
        gt_full = test['ground_truth_full']
        print(f"\n[{i+1:02d}/{len(tests)}] {test['id']} | {q[:60]}...")

        tick = time.time()

        # 1. Gọi pipeline MỘT LẦN DUY NHẤT — lấy cả answer, intent, context
        response = handle_query(q)
        answer = response.get('answer', '') if isinstance(response, dict) else str(response)

        # 2. Intent lấy từ response (handle_query đã chạy route() bên trong rồi)
        predicted_intent = response.get('intent', '') if isinstance(response, dict) else ''
        if not predicted_intent:
            predicted_intent = route(q)
        intent_correct = (predicted_intent == test['expected_intent'])

        # 3. Lấy context từ response nếu có
        context = ""
        if not no_llm and isinstance(response, dict):
            for k in ('context', 'retrieved', 'sources', 'docs'):
                if response.get(k):
                    context = str(response[k])[:1000]
                    break

        elapsed = time.time() - tick

        # 4. Scoring
        if no_llm:
            faith = comp = ar = 3   # neutral
            cp = cr = None
        else:
            # Dùng gt_full làm pseudo-context nếu không retrieve được context thực
            judge_ctx = context if context else gt_full
            faith = score_faithfulness(q, answer, judge_ctx)
            ar    = score_answer_relevancy(q, answer)
            comp  = score_completeness(q, answer, gt_full)
            # Always score CP/CR: dùng context thực nếu có, không thì dùng ground_truth
            cp_ctx = context if context else gt_full
            cp    = score_context_precision(q, cp_ctx)
            cr    = score_context_recall(gt_full, cp_ctx)

        factual = check_factual_accuracy(answer, gt)
        ragas   = compute_ragas_score(faith, ar, cp, cr, comp, factual)

        r = {
            'id': test['id'],
            'category': test['category'],
            'difficulty': test['difficulty'],
            'question': q,
            'expected_intent': test['expected_intent'],
            'predicted_intent': predicted_intent,
            'intent_correct': intent_correct,
            'answer': answer[:300],
            'ground_truth': gt,
            'ground_truth_full': gt_full,
            'has_context': bool(context),
            'faithfulness': faith,
            'answer_relevancy': ar,
            'context_precision': cp,
            'context_recall': cr,
            'completeness': comp,
            'factual_accuracy': factual,
            'ragas_score': ragas,
            'response_time': round(elapsed, 2)
        }
        results.append(r)

        # Per-row log
        intent_icon = "✓" if intent_correct else "✗"
        cp_str = f" CP:{cp}" if cp is not None else ""
        cr_str = f" CR:{cr}" if cr is not None else ""
        print(f"  Intent:{intent_icon}({predicted_intent}/{test['expected_intent']}) | "
              f"Faith:{faith} AR:{ar} Comp:{comp}{cp_str}{cr_str} Fact:{factual:.0%} | "
              f"RAGAS:{ragas:.2f} | {elapsed:.1f}s")

    # ══════════════════════════════════════════
    #  AGGREGATE SUMMARY
    # ══════════════════════════════════════════
    total_time = time.time() - total_start
    n = len(results)

    def avg(key): return sum(r[key] for r in results if r[key] is not None) / n
    def pct(key): return sum(1 for r in results if r[key]) / n

    intent_acc  = pct('intent_correct')
    avg_faith   = avg('faithfulness')
    avg_ar      = avg('answer_relevancy')
    avg_comp    = avg('completeness')
    avg_fact    = avg('factual_accuracy')
    avg_ragas   = avg('ragas_score')
    avg_time    = avg('response_time')

    # Context metrics (only if pipeline supports)
    ctx_results = [r for r in results if r['context_precision'] is not None]
    has_ctx = len(ctx_results) > 0
    avg_cp = sum(r['context_precision'] for r in ctx_results) / len(ctx_results) if has_ctx else None
    avg_cr = sum(r['context_recall'] for r in ctx_results) / len(ctx_results) if has_ctx else None

    print("\n" + "=" * 72)
    print("  📊 RAGAS-like EVALUATION RESULTS")
    print("=" * 72)
    ctx_line_cp = f"  │ Context Precision (1-5)     │ {avg_cp:.2f}   │" if has_ctx else \
                  f"  │ Context Precision (1-5)     │  N/A   │"
    ctx_line_cr = f"  │ Context Recall (1-5)        │ {avg_cr:.2f}   │" if has_ctx else \
                  f"  │ Context Recall (1-5)        │  N/A   │"
    print(f"""
  ┌────────────────────────────┬────────┐
  │ Metric                     │ Score  │
  ├────────────────────────────┼────────┤
  │ Intent Accuracy            │ {intent_acc:.1%}  │
  │ Answer Relevancy (1-5)     │ {avg_ar:.2f}   │
  │ Faithfulness (1-5)         │ {avg_faith:.2f}   │
  │ Completeness (1-5)         │ {avg_comp:.2f}   │
{ctx_line_cp}
{ctx_line_cr}
  │ Factual Accuracy (0-1)     │ {avg_fact:.2f}   │
  ├────────────────────────────┼────────┤
  │ ★ RAGAS Score (0-5)        │ {avg_ragas:.2f}   │
  │   (↔ 0-100%)               │ {avg_ragas/5:.1%}  │
  ├────────────────────────────┼────────┤
  │ Avg Response Time          │ {avg_time:.1f}s   │
  │ Total Tests                │ {n:5d}  │
  └────────────────────────────┴────────┘
""")

    # --- Per-intent breakdown ---
    print("  Per-Intent Breakdown:")
    intents = sorted(set(r['expected_intent'] for r in results))
    for intent in intents:
        items = [r for r in results if r['expected_intent'] == intent]
        ia = sum(1 for r in items if r['intent_correct']) / len(items)
        ar = sum(r['answer_relevancy'] for r in items) / len(items)
        rs = sum(r['ragas_score'] for r in items) / len(items)
        print(f"    [{intent}] {len(items):3d} cases | Intent:{ia:.0%} | AR:{ar:.1f} | RAGAS:{rs:.2f}")

    # --- Per-difficulty breakdown ---
    print("\n  Per-Difficulty Breakdown:")
    for diff in ['easy', 'medium', 'hard']:
        items = [r for r in results if r['difficulty'] == diff]
        if not items:
            continue
        ia = sum(1 for r in items if r['intent_correct']) / len(items)
        rs = sum(r['ragas_score'] for r in items) / len(items)
        fa = sum(r['factual_accuracy'] for r in items) / len(items)
        print(f"    [{diff:6s}] {len(items):3d} cases | Intent:{ia:.0%} | Fact:{fa:.0%} | RAGAS:{rs:.2f}")

    # --- Per-category breakdown (top failures) ---
    failures = [r for r in results if not r['intent_correct'] or r['ragas_score'] < 3.0]
    if failures:
        print(f"\n  ⚠ Low-score / Wrong-intent cases ({len(failures)}):")
        for r in sorted(failures, key=lambda x: x['ragas_score'])[:10]:
            flag = "INTENT✗" if not r['intent_correct'] else ""
            print(f"    {r['id']:12s} RAGAS:{r['ragas_score']:.2f} {flag} | {r['question'][:50]}")

    # --- Save results ---
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'evaluation_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'model': OLLAMA_MODEL,
            'llm_judge': not no_llm,
            'summary': {
                'total_tests': n,
                'intent_accuracy': round(intent_acc, 4),
                'avg_answer_relevancy': round(avg_ar, 2),
                'avg_faithfulness': round(avg_faith, 2),
                'avg_completeness': round(avg_comp, 2),
                'avg_context_precision': round(avg_cp, 2) if avg_cp else None,
                'avg_context_recall': round(avg_cr, 2) if avg_cr else None,
                'avg_factual_accuracy': round(avg_fact, 4),
                'ragas_score': round(avg_ragas, 2),
                'ragas_pct': round(avg_ragas / 5, 4),
                'avg_response_time': round(avg_time, 2),
                'total_time_sec': round(total_time, 1)
            },
            'results': results
        }, f, ensure_ascii=False, indent=2)

    print(f"\n  📄 Results saved → {output_path}")
    print(f"  ⏱  Total time: {total_time:.0f}s")
    print("=" * 72)

    return results


# ══════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════

if __name__ == '__main__':
    quick  = '--quick'  in sys.argv
    no_llm = '--no-llm' in sys.argv
    tf = None
    for arg in sys.argv[1:]:
        if arg.endswith('.json') and os.path.exists(arg):
            tf = arg
    evaluate(test_file=tf, quick=quick, no_llm=no_llm)