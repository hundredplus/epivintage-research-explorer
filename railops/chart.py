"""Generate a dependency-free, accessible SVG from actual scenario metrics."""
from html import escape


def chart(rows):
    labels = ['Four minute service', 'Three minute service',
              'Add timetable recovery', 'Lower dwell variability']
    maximum = max(1, max(r['mean_terminal_delay_seconds'] for r in rows))
    scale = 610 / maximum
    desc = ', '.join(f"{r['mean_terminal_delay_seconds']:.1f}" for r in rows)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 390" role="img" aria-labelledby="chart-title chart-desc">',
             '<title id="chart-title">Mean terminal delay under four synthetic scenarios</title>',
             f'<desc id="chart-desc">Mean delays in seconds: {desc}. Model outputs, not observed railway performance.</desc>',
             '<rect width="1000" height="390" fill="#f2f6f8"/>',
             '<g font-family="Arial,sans-serif" fill="#18283b">',
             '<text x="30" y="37" font-size="23" font-weight="bold">Mean terminal delay</text>',
             f'<text x="30" y="64" font-size="15">Synthetic corridor | {rows[0]["replications"]} replications | seed {rows[0]["seed"]} | seconds</text>']
    for i, (label, row) in enumerate(zip(labels, rows)):
        y = 95 + 61 * i
        value = row['mean_terminal_delay_seconds']
        color = '#ad543c' if i == 1 else '#287785'
        parts.extend([f'<text x="30" y="{y+23}" font-size="16">{escape(label)}</text>',
                      f'<rect x="255" y="{y}" width="{value*scale:.2f}" height="34" fill="{color}" rx="3"/>',
                      f'<text x="{267+value*scale:.2f}" y="{y+23}" font-size="17">{value:.1f}</text>'])
    parts.extend(['<text x="30" y="365" font-size="14">Recovery extends the scheduled journey by 60 s. Compare the full metrics before judging benefits.</text>', '</g></svg>'])
    return '\n'.join(parts)
