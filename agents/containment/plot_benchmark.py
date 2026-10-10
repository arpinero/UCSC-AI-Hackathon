"""Optional publication figure from actual outcome JSON; requires matplotlib."""
import argparse
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source'); parser.add_argument('--output-prefix', required=True)
    args = parser.parse_args(); source = Path(args.source)
    data = json.loads(source.read_text())
    if data.get('mode') != 'model' or not data.get('results'):
        raise ValueError('Figure requires actual nonempty model inference results')
    summary = data['summary']; rows = data['results']
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle('Containment outcome benchmark', fontsize=20, fontweight='bold', y=.985)
    complete = summary['completed'] == data['planned']
    fig.text(.5, .948, f"{data['config']['model']} | {'COMPLETE' if complete else 'PARTIAL'}: "
             f"{summary['passed']}/{summary['completed']} passed; {data['planned']} planned", ha='center', fontsize=12)
    ax = axes[0, 0]; groups = summary['families']; labels = list(groups)
    passes = [groups[k]['passed'] for k in labels]
    failures = [groups[k]['completed'] - groups[k]['passed'] for k in labels]
    ax.barh(labels, passes, color='#138a74', label='Passed')
    ax.barh(labels, failures, left=passes, color='#c94848', label='Failed')
    for i, k in enumerate(labels):
        ax.text(groups[k]['completed'] + .07, i, f"{groups[k]['passed']}/{groups[k]['completed']}", va='center', fontsize=9)
    ax.invert_yaxis(); ax.set_xlim(0, max(groups[k]['completed'] for k in labels) + .7)
    ax.set_title('A. Response-family coverage'); ax.set_xlabel('Completed cases (correlated seed variants)')
    ax.legend(loc='lower right'); ax.tick_params(axis='y', labelsize=9)
    ax = axes[0, 1]
    times = [a['result']['latency_seconds'] for r in rows for a in r['inference']
             if 'latency_seconds' in a['result']]
    ax.hist(times, bins=min(12, max(4, len(times)//4)), color='#397aad', alpha=.8)
    for label, key, color in [('Median', 'p50', '#138a74'), ('p95', 'p95', '#b26710')]:
        if summary['latency_seconds'][key] is not None:
            value = summary['latency_seconds'][key]
            ax.axvline(value, color=color, label=f'{label}: {value:.2f}s')
    ax.axvline(120, color='#c94848', linestyle='--', label='Authored deadline: 120s')
    ax.set_title('B. Measured end-to-end inference latency')
    ax.set_xlabel('Seconds (includes correction, queue/load time)'); ax.set_ylabel('Responses'); ax.legend(fontsize=9)
    ax = axes[1, 0]
    variants = [('No response', 'no_response'), ('Model', 'outcomes'),
                ('Matched reference', 'latency_matched_fixture_reference'),
                ('Instant reference', 'instant_fixture_reference')]
    totals = [sum(r[key]['bytes_lost'] for r in rows)/1e6 for _, key in variants]
    bars = ax.bar([label for label, _ in variants], totals, color=['#7d8791', '#138a74', '#397aad', '#9373aa'])
    ax.bar_label(bars, labels=[f'{v:.2f}' for v in totals], padding=4)
    ax.set_ylim(0, max(1, max(totals)*1.2)); ax.set_ylabel('Simulated bytes lost (decimal MB, summed across cases)')
    ax.set_title('C. Exfiltration counterfactuals'); ax.tick_params(axis='x', labelsize=9)
    ax = axes[1, 1]
    totals = [sum(r[key]['service_disruption_seconds'] for r in rows) for _, key in variants]
    bars = ax.bar([label for label, _ in variants], totals, color=['#7d8791', '#138a74', '#397aad', '#9373aa'])
    ax.bar_label(bars, labels=[f'{v:.1f}' for v in totals], padding=4)
    ax.set_ylim(0, max(1, max(totals)*1.2)); ax.set_ylabel('Simulated service-disruption seconds (sum across cases)')
    ax.set_title(f"D. Availability cost | authorized false positives: "
                 f"{summary['benign_false_positive_incidents']}/{summary['benign_incidents']}")
    ax.tick_params(axis='x', labelsize=9)
    for ax in axes.flat:
        ax.spines[['top', 'right']].set_visible(False)
        ax.set_axisbelow(True); ax.grid(axis='x' if ax is axes[0, 0] else 'y', alpha=.18)
    fig.text(.5, .018, 'Measured model inference; authored simulated harm and dependencies. '
             'References know fixture truth. No real attacks, population accuracy or MITRE endorsement.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, .915))
    prefix = Path(args.output_prefix); prefix.parent.mkdir(parents=True, exist_ok=True)
    for extension in ('png', 'svg', 'pdf'):
        fig.savefig(prefix.with_suffix('.'+extension), dpi=180)
    prefix.with_suffix('.provenance.json').write_text(json.dumps({
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'plot_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'matplotlib': matplotlib.__version__, 'source_config': data['config'],
        'complete': complete, 'completed': summary['completed'], 'planned': data['planned']}, indent=2))
    plt.close(fig)


if __name__ == '__main__':
    main()
