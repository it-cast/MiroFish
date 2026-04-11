"""
AUGUR — Gerador de PDF Profissional v2.0
PDF com gráficos matplotlib embutidos, 3 camadas de profundidade,
design premium e executive summary de 1 página.

Requer: pip install fpdf2 matplotlib
"""
import io
import json
import os
import re
import logging
import textwrap
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

try:
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    FPDF = object
    HAS_FPDF = False
    logger.warning("fpdf2 não instalado.")

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("matplotlib não instalado. Gráficos desabilitados.")


# ═══════════════════════════════════════════════════════════
# PALETA DE CORES
# ═══════════════════════════════════════════════════════════
class Colors:
    # PDF colors (RGB 0-255)
    BG = (249, 249, 252)
    SURFACE = (255, 255, 255)
    TEXT = (26, 26, 46)
    MUTED = (120, 120, 150)
    LIGHT = (200, 200, 215)
    ACCENT = (0, 229, 195)
    ACCENT2 = (124, 111, 247)
    DANGER = (255, 90, 90)
    GOLD = (245, 166, 35)
    SUCCESS = (46, 204, 113)
    
    # Matplotlib colors (0-1 float)
    @staticmethod
    def mpl(rgb):
        return tuple(c / 255 for c in rgb)


# ═══════════════════════════════════════════════════════════
# CHART GENERATORS (matplotlib → PNG bytes)
# ═══════════════════════════════════════════════════════════
class ChartGenerator:
    """Gera gráficos como imagens PNG em memória."""
    
    DPI = 150
    
    @classmethod
    def _fig_to_bytes(cls, fig) -> bytes:
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=cls.DPI, bbox_inches='tight',
                    facecolor='white', edgecolor='none', transparent=False)
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    
    @classmethod
    def verdict_gauge(cls, verdict: str) -> bytes:
        """Gauge semicircular do veredicto: GO / AJUSTAR / NO-GO."""
        fig, ax = plt.subplots(figsize=(4, 2.2))
        ax.set_xlim(-1.3, 1.3)
        ax.set_ylim(-0.3, 1.3)
        ax.set_aspect('equal')
        ax.axis('off')
        
        # Arco de fundo
        angles_bg = np.linspace(np.pi, 0, 100)
        for i in range(len(angles_bg) - 1):
            t = i / len(angles_bg)
            if t < 0.33:
                color = Colors.mpl(Colors.DANGER)
            elif t < 0.66:
                color = Colors.mpl(Colors.GOLD)
            else:
                color = Colors.mpl(Colors.SUCCESS)
            ax.plot([np.cos(angles_bg[i]), np.cos(angles_bg[i+1])],
                    [np.sin(angles_bg[i]), np.sin(angles_bg[i+1])],
                    color=color, linewidth=18, solid_capstyle='butt')
        
        # Ponteiro
        v = verdict.upper().strip()
        if 'GO' == v or v.startswith('GO'):
            angle = np.pi * 0.15
            needle_color = Colors.mpl(Colors.SUCCESS)
        elif 'NO' in v or 'NÃO' in v:
            angle = np.pi * 0.85
            needle_color = Colors.mpl(Colors.DANGER)
        else:  # AJUSTAR
            angle = np.pi * 0.5
            needle_color = Colors.mpl(Colors.GOLD)
        
        ax.annotate('', xy=(0.7 * np.cos(angle), 0.7 * np.sin(angle)),
                     xytext=(0, 0),
                     arrowprops=dict(arrowstyle='->', color=needle_color, lw=2.5))
        ax.plot(0, 0, 'o', color=Colors.mpl(Colors.TEXT), markersize=6, zorder=5)
        
        # Labels
        ax.text(-1.1, -0.15, 'NO-GO', ha='center', fontsize=7, color=Colors.mpl(Colors.DANGER), fontweight='bold')
        ax.text(0, 1.15, 'AJUSTAR', ha='center', fontsize=7, color=Colors.mpl(Colors.GOLD), fontweight='bold')
        ax.text(1.1, -0.15, 'GO', ha='center', fontsize=7, color=Colors.mpl(Colors.SUCCESS), fontweight='bold')
        ax.text(0, -0.25, v, ha='center', fontsize=11, color=Colors.mpl(Colors.TEXT), fontweight='bold')
        
        fig.patch.set_facecolor('white')
        return cls._fig_to_bytes(fig)
    
    @classmethod
    def scenario_bars(cls, scenarios: List[Dict]) -> bytes:
        """Barras horizontais dos cenários com probabilidades."""
        fig, ax = plt.subplots(figsize=(6, 1.8))
        
        if not scenarios:
            scenarios = [
                {"name": "Cenário Otimista", "probability": 45},
                {"name": "Cenário Base", "probability": 35},
                {"name": "Cenário Pessimista", "probability": 20},
            ]
        
        names = [s.get("name", f"Cenário {i+1}")[:40] for i, s in enumerate(scenarios)]
        probs = [s.get("probability", 33) for s in scenarios]
        colors_list = [Colors.mpl(Colors.SUCCESS), Colors.mpl(Colors.GOLD), Colors.mpl(Colors.DANGER)]
        
        # Extend colors if more scenarios
        while len(colors_list) < len(names):
            colors_list.append(Colors.mpl(Colors.ACCENT2))
        
        y_pos = range(len(names))
        bars = ax.barh(y_pos, probs, color=colors_list[:len(names)], height=0.5, 
                       edgecolor='white', linewidth=0.5)
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(names, fontsize=7)
        ax.set_xlabel('Probabilidade (%)', fontsize=7)
        ax.set_xlim(0, 100)
        ax.invert_yaxis()
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.tick_params(labelsize=7)
        
        for bar, prob in zip(bars, probs):
            ax.text(bar.get_width() + 1.5, bar.get_y() + bar.get_height()/2,
                    f'{prob}%', va='center', fontsize=8, fontweight='bold',
                    color=Colors.mpl(Colors.TEXT))
        
        fig.patch.set_facecolor('white')
        plt.tight_layout()
        return cls._fig_to_bytes(fig)
    
    @classmethod
    def risk_matrix(cls, risks: List[Dict]) -> bytes:
        """Matriz de risco probabilidade × impacto."""
        fig, ax = plt.subplots(figsize=(5, 3.5))
        
        impact_map = {"baixo": 1, "médio": 2, "medio": 2, "médio-alto": 2.5, 
                      "alto": 3, "crítico": 3.5, "low": 1, "medium": 2, "high": 3}
        
        for i, r in enumerate(risks[:7]):
            prob = r.get("probability", 50)
            imp_str = r.get("impact", "médio").lower()
            imp = impact_map.get(imp_str, 2)
            
            # Color by severity
            severity = prob * imp / 3
            if severity > 60:
                color = Colors.mpl(Colors.DANGER)
            elif severity > 30:
                color = Colors.mpl(Colors.GOLD)
            else:
                color = Colors.mpl(Colors.SUCCESS)
            
            ax.scatter(prob, imp, s=200, c=[color], edgecolors='white', linewidth=1, zorder=3)
            name = r.get("name", f"R{i+1}")
            short_name = name[:25] + "..." if len(name) > 25 else name
            ax.annotate(f"R{i+1}", (prob, imp), fontsize=6, ha='center', va='center',
                       fontweight='bold', color='white', zorder=4)
        
        ax.set_xlabel('Probabilidade (%)', fontsize=8)
        ax.set_ylabel('Impacto', fontsize=8)
        ax.set_xlim(0, 100)
        ax.set_ylim(0.5, 3.8)
        ax.set_yticks([1, 2, 3])
        ax.set_yticklabels(['Baixo', 'Médio', 'Alto'], fontsize=7)
        ax.tick_params(labelsize=7)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        # Background gradient zones
        ax.axhspan(0.5, 1.5, alpha=0.05, color='green')
        ax.axhspan(1.5, 2.5, alpha=0.05, color='orange')
        ax.axhspan(2.5, 3.8, alpha=0.05, color='red')
        
        # Legend
        if risks:
            legend_text = "\n".join([f"R{i+1}: {r.get('name', '')[:35]}" for i, r in enumerate(risks[:7])])
            ax.text(1.02, 0.98, legend_text, transform=ax.transAxes, fontsize=5.5,
                    verticalalignment='top', fontfamily='monospace',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='#eee'))
        
        fig.patch.set_facecolor('white')
        plt.tight_layout()
        return cls._fig_to_bytes(fig)
    
    @classmethod
    def emotion_radar(cls, emotions: Dict[str, float]) -> bytes:
        """Radar chart das emoções."""
        fig, ax = plt.subplots(figsize=(3.5, 3.5), subplot_kw=dict(polar=True))
        
        if not emotions:
            emotions = {"Confiança": 31, "Ceticismo": 24, "Empolgação": 18,
                       "Medo": 12, "FOMO": 9, "Indiferença": 6}
        
        labels = list(emotions.keys())
        values = list(emotions.values())
        
        # Complete the circle
        angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
        values_plot = values + [values[0]]
        angles_plot = angles + [angles[0]]
        
        ax.plot(angles_plot, values_plot, 'o-', linewidth=2, 
                color=Colors.mpl(Colors.ACCENT2), markersize=5)
        ax.fill(angles_plot, values_plot, alpha=0.15, color=Colors.mpl(Colors.ACCENT2))
        
        ax.set_xticks(angles)
        ax.set_xticklabels(labels, fontsize=7)
        ax.set_ylim(0, max(values) * 1.2)
        ax.tick_params(labelsize=6)
        ax.grid(color='#ddd', linewidth=0.5)
        
        # Add value labels
        for angle, val in zip(angles, values):
            ax.text(angle, val + max(values) * 0.08, f'{val}%', ha='center', 
                    fontsize=7, fontweight='bold', color=Colors.mpl(Colors.TEXT))
        
        fig.patch.set_facecolor('white')
        plt.tight_layout()
        return cls._fig_to_bytes(fig)
    
    @classmethod
    def timeline_milestones(cls, milestones: List[Dict] = None) -> bytes:
        """Timeline horizontal de marcos dos 24 meses."""
        fig, ax = plt.subplots(figsize=(6.5, 2))
        
        if not milestones:
            milestones = [
                {"month": 0, "label": "Lançamento", "type": "start"},
                {"month": 3, "label": "Fim curiosidade\ninicial", "type": "warning"},
                {"month": 6, "label": "Teste de\nconsistência", "type": "neutral"},
                {"month": 10, "label": "Break-even\n(cenário base)", "type": "success"},
                {"month": 15, "label": "Consolidação\nou fragilidade", "type": "warning"},
                {"month": 24, "label": "Permanência\nlegitimada", "type": "success"},
            ]
        
        type_colors = {
            "start": Colors.mpl(Colors.ACCENT2),
            "success": Colors.mpl(Colors.SUCCESS),
            "warning": Colors.mpl(Colors.GOLD),
            "danger": Colors.mpl(Colors.DANGER),
            "neutral": Colors.mpl(Colors.MUTED),
        }
        
        # Base line
        ax.plot([0, 24], [0, 0], color='#ddd', linewidth=2, zorder=1)
        
        for i, m in enumerate(milestones):
            month = m["month"]
            color = type_colors.get(m.get("type", "neutral"), Colors.mpl(Colors.MUTED))
            y_offset = 0.5 if i % 2 == 0 else -0.5
            
            ax.scatter(month, 0, s=80, c=[color], zorder=3, edgecolors='white', linewidth=1)
            ax.plot([month, month], [0, y_offset * 0.6], color=color, linewidth=1, zorder=2)
            ax.text(month, y_offset * 0.75, m["label"], ha='center', va='center',
                    fontsize=5.5, color=Colors.mpl(Colors.TEXT), fontweight='bold')
        
        ax.set_xlim(-1, 25)
        ax.set_ylim(-1, 1)
        ax.axis('off')
        
        # Month markers
        for m in [0, 6, 12, 18, 24]:
            ax.text(m, -0.85, f'M{m}', ha='center', fontsize=6, color=Colors.mpl(Colors.MUTED))
        
        fig.patch.set_facecolor('white')
        plt.tight_layout()
        return cls._fig_to_bytes(fig)
    
    @classmethod
    def kpi_summary(cls, kpis: List[Dict]) -> bytes:
        """Cards de KPI visuais."""
        n = min(len(kpis), 5)
        if n == 0:
            return b''
        
        fig, axes = plt.subplots(1, n, figsize=(6.5, 1.3))
        if n == 1:
            axes = [axes]
        
        colors_cycle = [Colors.ACCENT, Colors.ACCENT2, Colors.SUCCESS, Colors.GOLD, Colors.DANGER]
        
        for i, (ax, kpi) in enumerate(zip(axes, kpis[:5])):
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
            
            color = Colors.mpl(colors_cycle[i % len(colors_cycle)])
            
            # Card background
            rect = FancyBboxPatch((0.05, 0.05), 0.9, 0.9, boxstyle="round,pad=0.05",
                                   facecolor='#f8f8fc', edgecolor='#eeeef2', linewidth=0.5)
            ax.add_patch(rect)
            
            # Value
            val = str(kpi.get("value", "—"))
            ax.text(0.5, 0.6, val, ha='center', va='center', fontsize=14,
                    fontweight='bold', color=color)
            
            # Label
            label = kpi.get("label", "")[:20]
            ax.text(0.5, 0.25, label, ha='center', va='center', fontsize=5.5,
                    color=Colors.mpl(Colors.MUTED))
        
        fig.patch.set_facecolor('white')
        plt.tight_layout()
        return cls._fig_to_bytes(fig)
    
    @classmethod
    def force_map(cls, forces: List[Dict] = None) -> bytes:
        """Mapa de forças simplificado."""
        fig, ax = plt.subplots(figsize=(5, 3.5))
        ax.set_xlim(-2, 2)
        ax.set_ylim(-2, 2)
        ax.axis('off')
        
        if not forces:
            forces = [
                {"name": "Incumbente\n(dominante)", "x": -0.8, "y": 0.8, "size": 1.0, "type": "resist"},
                {"name": "Marketplaces\n(preço)", "x": 0.8, "y": 0.8, "size": 0.8, "type": "resist"},
                {"name": "Sacoleiras\n(conveniência)", "x": -0.8, "y": -0.5, "size": 0.5, "type": "neutral"},
                {"name": "Nova Loja\n(entrante)", "x": 0.3, "y": -0.3, "size": 0.4, "type": "support"},
            ]
        
        type_colors = {
            "resist": Colors.mpl(Colors.DANGER),
            "support": Colors.mpl(Colors.SUCCESS),
            "neutral": Colors.mpl(Colors.GOLD),
        }
        
        for f in forces:
            color = type_colors.get(f.get("type", "neutral"), Colors.mpl(Colors.MUTED))
            size = f.get("size", 0.5) * 500
            ax.scatter(f["x"], f["y"], s=size, c=[color], alpha=0.3, zorder=2)
            ax.scatter(f["x"], f["y"], s=size * 0.3, c=[color], alpha=0.7, zorder=3)
            ax.text(f["x"], f["y"] - 0.35 * f.get("size", 0.5), f["name"],
                    ha='center', va='top', fontsize=6, fontweight='bold',
                    color=Colors.mpl(Colors.TEXT))
        
        ax.set_title('Mapa de Forças Competitivas', fontsize=9, fontweight='bold',
                     color=Colors.mpl(Colors.TEXT), pad=10)
        
        # Legend
        for i, (label, color) in enumerate([("Resistência", Colors.mpl(Colors.DANGER)),
                                              ("Neutro", Colors.mpl(Colors.GOLD)),
                                              ("Apoio", Colors.mpl(Colors.SUCCESS))]):
            ax.scatter([], [], c=[color], s=40, label=label)
        ax.legend(loc='lower right', fontsize=6, framealpha=0.8)
        
        fig.patch.set_facecolor('white')
        plt.tight_layout()
        return cls._fig_to_bytes(fig)


# ═══════════════════════════════════════════════════════════
# PDF BUILDER
# ═══════════════════════════════════════════════════════════

class AugurPDF(FPDF):
    """PDF customizado AUGUR com header/footer."""
    
    def __init__(self, report_title: str = "Relatório de Previsão"):
        if not HAS_FPDF:
            raise ImportError("fpdf2 não instalado")
        super().__init__()
        self.report_title = report_title
        self.set_auto_page_break(auto=True, margin=25)
        self._section_num = 0
        self._total_sections = 0
    
    def header(self):
        if self.page_no() <= 2:
            return
        self.set_font("Helvetica", "B", 7)
        self.set_text_color(*Colors.MUTED)
        self.cell(0, 6, f"AUGUR {self._c(self.report_title[:70])}", align="L")
        self.ln(1)
        self.set_draw_color(*Colors.ACCENT)
        self.set_line_width(0.4)
        self.line(10, 12, self.w - 10, 12)
        self.ln(6)
    
    def footer(self):
        if self.page_no() <= 2:
            return
        self.set_y(-18)
        self.set_draw_color(*Colors.LIGHT)
        self.set_line_width(0.15)
        self.line(10, self.get_y(), self.w - 10, self.get_y())
        self.ln(3)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*Colors.MUTED)
        self.cell(self.w / 2 - 10, 5, "augur.itcast.com.br")
        self.cell(self.w / 2 - 10, 5, self._c(f"Página {self.page_no() - 2}"), align="R")
    
    @staticmethod
    def _c(text: str) -> str:
        """Sanitiza para Latin-1 (fpdf2 Helvetica)."""
        if not text:
            return ""
        replacements = {
            '\u2014': '-', '\u2013': '-', '\u2018': "'", '\u2019': "'",
            '\u201c': '"', '\u201d': '"', '\u2022': '-', '\u2026': '...',
            '\u00a0': ' ', '\u200b': '', '\u2212': '-', '\u00b2': '2',
            '\u00b3': '3', '\u2019': "'", '\u2190': '<-', '\u2192': '->',
            '\u2264': '<=', '\u2265': '>=', '\u00b1': '+/-', '\u2248': '~',
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text.encode('latin-1', errors='replace').decode('latin-1')


class PDFGenerator:
    """Gera PDF profissional do relatório AUGUR."""
    
    # Seções EXECUTIVE (1-pager + cenários + riscos + recomendações)
    EXECUTIVE_SECTIONS = {
        "Resumo Executivo", "Cenários Futuros", "Cenários", "Fatores de Risco", 
        "Riscos", "Recomendações Estratégicas", "Recomendações"
    }
    
    # Seções STANDARD (executive + análise emocional + mapa + cronologia + comunicação + previsões)
    STANDARD_SECTIONS = EXECUTIVE_SECTIONS | {
        "Análise Emocional", "Análise de Sentimento", "Mapa de Forças",
        "Cronologia da Simulação", "Cronologia", "Estratégia de Comunicação",
        "Previsões com Intervalo de Confiança", "Previsões"
    }
    
    @classmethod
    def generate(cls, report_data: Dict[str, Any], depth: str = "standard",
                 output_path: Optional[str] = None) -> bytes:
        """
        Gera PDF do relatório.
        
        Args:
            report_data: dict com title, summary, sections [{title, content}]
            depth: "executive" (~10pg), "standard" (~25pg), "deep" (~70pg)
            output_path: se fornecido, salva em disco
        
        Returns: bytes do PDF
        """
        if not HAS_FPDF:
            raise ImportError("fpdf2 não instalado. pip install fpdf2")
        
        title = report_data.get("title", "Relatório de Previsão AUGUR")
        summary = report_data.get("summary", "")
        sections = report_data.get("sections", [])
        
        # Extract verdict from title or summary
        verdict = cls._extract_verdict(title, summary)
        
        # Parse structured data from sections
        scenarios = cls._parse_scenarios(sections)
        risks = cls._parse_risks(sections)
        emotions = cls._parse_emotions(sections)
        kpis = cls._parse_kpis(summary)
        
        pdf = AugurPDF(report_title=title)
        pdf._total_sections = len(sections)
        
        # ═══ CAPA ═══
        cls._render_cover(pdf, title, summary, verdict)
        
        # ═══ EXECUTIVE SUMMARY (1 page visual) ═══
        cls._render_executive_page(pdf, verdict, summary, scenarios, kpis)
        
        # ═══ SUMÁRIO ═══
        filtered_sections = cls._filter_sections(sections, depth)
        cls._render_toc(pdf, filtered_sections)
        
        # ═══ SEÇÕES ═══
        for i, section in enumerate(filtered_sections):
            sec_title = section.get("title", f"Seção {i+1}")
            content = section.get("content", "")
            
            pdf._section_num = i + 1
            
            # Section title page
            cls._render_section_header(pdf, i + 1, len(filtered_sections), sec_title)
            
            # Charts for specific sections
            if HAS_MATPLOTLIB:
                cls._render_section_charts(pdf, sec_title, scenarios, risks, emotions)
            
            # Text content
            if depth == "executive":
                content = cls._truncate_content(content, max_chars=3000)
            elif depth == "standard":
                content = cls._truncate_content(content, max_chars=8000)
            # deep = full content
            
            cls._render_section_content(pdf, content)
        
        # ═══ CONTRA-CAPA ═══
        cls._render_back_cover(pdf, verdict)
        
        # Output
        pdf_bytes = pdf.output()
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
            logger.info(f"PDF salvo: {output_path} ({len(pdf_bytes)} bytes)")
        
        return pdf_bytes
    
    # ─────────────────────────────────────────────────
    # PARSERS: extraem dados estruturados do markdown
    # ─────────────────────────────────────────────────
    
    @staticmethod
    def _extract_verdict(title: str, summary: str) -> str:
        combined = f"{title} {summary}".upper()
        if "NO-GO" in combined or "NO GO" in combined or "NÃO-GO" in combined:
            return "NO-GO"
        elif "AJUSTAR" in combined:
            return "AJUSTAR"
        elif "GO" in combined:
            return "GO"
        return "AJUSTAR"
    
    @staticmethod
    def _parse_scenarios(sections: List[Dict]) -> List[Dict]:
        """Extrai cenários com probabilidades."""
        scenarios = []
        for sec in sections:
            title = sec.get("title", "").lower()
            if "cenário" in title or "cenario" in title or "futuro" in title:
                content = sec.get("content", "")
                # Pattern: Cenário N: Name ... Probabilidade: XX%
                pattern = r'(?:Cen[aá]rio\s*\d*[:\.]?\s*)(.+?)(?:\n|$).*?(?:[Pp]robabilidade[:\s]*(\d+)%)'
                matches = re.findall(pattern, content, re.DOTALL)
                for name, prob in matches:
                    name = name.strip().rstrip(':').strip()
                    if name and len(name) > 3:
                        scenarios.append({"name": name[:50], "probability": int(prob)})
                
                if not scenarios:
                    # Fallback: look for probability patterns
                    prob_matches = re.findall(r'[Pp]robabilidade[:\s]*(\d+)%', content)
                    for i, p in enumerate(prob_matches[:3]):
                        labels = ["Otimista", "Base", "Pessimista"]
                        scenarios.append({"name": f"Cenário {labels[i] if i < 3 else i+1}", 
                                         "probability": int(p)})
                break
        return scenarios
    
    @staticmethod
    def _parse_risks(sections: List[Dict]) -> List[Dict]:
        """Extrai riscos com probabilidade e impacto."""
        risks = []
        for sec in sections:
            title = sec.get("title", "").lower()
            if "risco" in title or "risk" in title:
                content = sec.get("content", "")
                # Pattern: #N Name ... Probabilidade: XX% ... Impacto: YYY
                blocks = re.split(r'(?:^|\n)#\d+\s+', content)
                for block in blocks[1:]:  # Skip pre-first-risk text
                    name_match = re.match(r'(.+?)(?:\n|$)', block)
                    prob_match = re.search(r'[Pp]robabilidade[:\s]*(\d+)%', block)
                    impact_match = re.search(r'[Ii]mpacto[:\s]*(Alto|Médio|Baixo|Médio-Alto|Crítico)', block, re.IGNORECASE)
                    
                    if name_match:
                        risks.append({
                            "name": name_match.group(1).strip()[:60],
                            "probability": int(prob_match.group(1)) if prob_match else 50,
                            "impact": impact_match.group(1) if impact_match else "Médio"
                        })
                break
        return risks
    
    @staticmethod
    def _parse_emotions(sections: List[Dict]) -> Dict[str, float]:
        """Extrai emoções com percentuais."""
        emotions = {}
        for sec in sections:
            title = sec.get("title", "").lower()
            if "emocional" in title or "sentimento" in title:
                content = sec.get("content", "")
                # Pattern: - Label: XX%  or  Label: XX%
                pattern = r'[-•]?\s*(\w[\w\sé]*?)\s*:\s*(\d+)%'
                matches = re.findall(pattern, content)
                for label, pct in matches:
                    label = label.strip()
                    if len(label) > 2 and len(label) < 25:
                        emotions[label] = float(pct)
                break
        return emotions
    
    @staticmethod
    def _parse_kpis(summary: str) -> List[Dict]:
        """Extrai KPIs do resumo executivo."""
        kpis = []
        # Pattern: **label**: valor  or  **label** valor
        pattern = r'\*\*(.+?)\*\*[:\s]*([^*\n]{3,40})'
        matches = re.findall(pattern, summary)
        for label, val in matches[:5]:
            kpis.append({"label": label.strip()[:20], "value": val.strip()[:15]})
        return kpis
    
    @classmethod
    def _filter_sections(cls, sections: List[Dict], depth: str) -> List[Dict]:
        """Filtra seções pelo nível de profundidade."""
        if depth == "deep":
            return sections
        
        target = cls.EXECUTIVE_SECTIONS if depth == "executive" else cls.STANDARD_SECTIONS
        filtered = []
        for sec in sections:
            title = sec.get("title", "")
            if any(t.lower() in title.lower() for t in target):
                filtered.append(sec)
        
        # If filtering removed too much, return all
        if len(filtered) < 3:
            return sections
        return filtered
    
    @staticmethod
    def _truncate_content(content: str, max_chars: int = 5000) -> str:
        """Trunca conteúdo preservando parágrafos completos."""
        if len(content) <= max_chars:
            return content
        
        # Cut at paragraph boundary
        truncated = content[:max_chars]
        last_para = truncated.rfind('\n\n')
        if last_para > max_chars * 0.6:
            truncated = truncated[:last_para]
        
        return truncated.rstrip() + "\n\n[...continua no relatório completo]"
    
    # ─────────────────────────────────────────────────
    # RENDERERS
    # ─────────────────────────────────────────────────
    
    @classmethod
    def _render_cover(cls, pdf: AugurPDF, title: str, summary: str, verdict: str):
        """Capa do relatório."""
        pdf.add_page()
        
        # Accent bar left
        pdf.set_fill_color(*Colors.ACCENT)
        pdf.rect(0, 0, 6, 297, "F")
        
        # Top accent line
        pdf.set_fill_color(*Colors.ACCENT2)
        pdf.rect(6, 0, 204, 3, "F")
        
        # Logo
        pdf.set_y(60)
        pdf.set_font("Helvetica", "B", 32)
        pdf.set_text_color(*Colors.TEXT)
        pdf.cell(0, 15, "AUGUR", align="C", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*Colors.MUTED)
        pdf.cell(0, 6, pdf._c("PLATAFORMA DE PREVISÃO DE MERCADO POR IA"), 
                align="C", new_x="LMARGIN", new_y="NEXT")
        
        pdf.ln(20)
        
        # Title
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*Colors.TEXT)
        clean_title = re.sub(r'Relatório de Previsão:\s*', '', title)
        clean_title = re.sub(r'\s*[-—]\s*(GO|NO-GO|AJUSTAR).*', '', clean_title, flags=re.IGNORECASE)
        pdf.multi_cell(0, 8, pdf._c(f"Relatório de Previsão: {clean_title}"), align="C")
        
        pdf.ln(8)
        
        # Verdict badge
        verdict_colors = {"GO": Colors.SUCCESS, "NO-GO": Colors.DANGER, "AJUSTAR": Colors.GOLD}
        badge_color = verdict_colors.get(verdict, Colors.GOLD)
        badge_text = f"VEREDICTO: {verdict}"
        
        badge_w = pdf.get_string_width(badge_text) + 20
        badge_x = (pdf.w - badge_w) / 2
        pdf.set_fill_color(*badge_color)
        pdf.rect(badge_x, pdf.get_y(), badge_w, 10, "F")
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 10, pdf._c(badge_text), align="C", new_x="LMARGIN", new_y="NEXT")
        
        pdf.ln(6)
        
        # Summary
        if summary:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*Colors.MUTED)
            # Remove "VEREDICTO: X." prefix
            clean_summary = re.sub(r'^VEREDICTO:\s*\w+[\.\!]?\s*', '', summary)
            pdf.set_x(25)
            pdf.multi_cell(pdf.w - 50, 5.5, pdf._c(clean_summary[:500]), align="C")
        
        # Date
        pdf.set_y(250)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*Colors.MUTED)
        now = datetime.now().strftime("%d/%m/%Y às %H:%M")
        pdf.cell(0, 5, pdf._c(f"{now}"), align="C")
    
    @classmethod
    def _render_executive_page(cls, pdf: AugurPDF, verdict: str, summary: str,
                                scenarios: List[Dict], kpis: List[Dict]):
        """Página visual de executive summary com gráficos."""
        if not HAS_MATPLOTLIB:
            return
        
        pdf.add_page()
        
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*Colors.TEXT)
        pdf.cell(0, 10, "Executive Summary", align="L", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_draw_color(*Colors.ACCENT)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 80, pdf.get_y())
        pdf.ln(6)
        
        # Verdict gauge
        try:
            gauge_bytes = ChartGenerator.verdict_gauge(verdict)
            gauge_path = "/tmp/augur_gauge.png"
            with open(gauge_path, 'wb') as f:
                f.write(gauge_bytes)
            pdf.image(gauge_path, x=60, w=80)
            os.unlink(gauge_path)
        except Exception as e:
            logger.warning(f"Erro ao gerar gauge: {e}")
        
        pdf.ln(4)
        
        # KPI cards
        if kpis:
            try:
                kpi_bytes = ChartGenerator.kpi_summary(kpis)
                if kpi_bytes:
                    kpi_path = "/tmp/augur_kpis.png"
                    with open(kpi_path, 'wb') as f:
                        f.write(kpi_bytes)
                    pdf.image(kpi_path, x=10, w=pdf.w - 20)
                    os.unlink(kpi_path)
            except Exception as e:
                logger.warning(f"Erro ao gerar KPIs: {e}")
        
        pdf.ln(4)
        
        # Scenario bars
        if scenarios:
            try:
                bars_bytes = ChartGenerator.scenario_bars(scenarios)
                bars_path = "/tmp/augur_scenarios.png"
                with open(bars_path, 'wb') as f:
                    f.write(bars_bytes)
                pdf.image(bars_path, x=15, w=pdf.w - 30)
                os.unlink(bars_path)
            except Exception as e:
                logger.warning(f"Erro ao gerar cenários: {e}")
    
    @classmethod
    def _render_toc(cls, pdf: AugurPDF, sections: List[Dict]):
        """Sumário."""
        pdf.add_page()
        
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(*Colors.TEXT)
        pdf.cell(0, 12, pdf._c("Sumário"), new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_draw_color(*Colors.ACCENT)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 50, pdf.get_y())
        pdf.ln(8)
        
        for i, sec in enumerate(sections):
            # Section number
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*Colors.ACCENT)
            num = f"{i+1:02d}"
            pdf.cell(12, 8, num)
            
            # Section title
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*Colors.TEXT)
            pdf.cell(0, 8, pdf._c(sec.get("title", f"Seção {i+1}")),
                    new_x="LMARGIN", new_y="NEXT")
            
            # Separator
            pdf.set_draw_color(*Colors.LIGHT)
            pdf.set_line_width(0.1)
            pdf.line(10, pdf.get_y(), pdf.w - 10, pdf.get_y())
            pdf.ln(2)
    
    @classmethod
    def _render_section_header(cls, pdf: AugurPDF, num: int, total: int, title: str):
        """Header de seção com número e título."""
        pdf.add_page()
        
        # Section tag
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*Colors.MUTED)
        pdf.cell(0, 6, pdf._c(f"SEÇÃO {num:02d} DE {total:02d}"), new_x="LMARGIN", new_y="NEXT")
        
        pdf.ln(2)
        
        # Title
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(*Colors.TEXT)
        pdf.multi_cell(0, 9, pdf._c(title))
        
        # Accent line
        pdf.set_draw_color(*Colors.ACCENT)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y() + 2, 60, pdf.get_y() + 2)
        pdf.ln(8)
    
    @classmethod
    def _render_section_charts(cls, pdf: AugurPDF, section_title: str,
                                scenarios: List[Dict], risks: List[Dict],
                                emotions: Dict[str, float]):
        """Adiciona gráficos relevantes antes do texto da seção."""
        title_lower = section_title.lower()
        chart_path = "/tmp/augur_chart.png"
        
        try:
            chart_bytes = None
            
            if ("cenário" in title_lower or "cenario" in title_lower or "futuro" in title_lower) and scenarios:
                chart_bytes = ChartGenerator.scenario_bars(scenarios)
            elif ("risco" in title_lower or "risk" in title_lower) and risks:
                chart_bytes = ChartGenerator.risk_matrix(risks)
            elif "emocional" in title_lower or "sentimento" in title_lower:
                chart_bytes = ChartGenerator.emotion_radar(emotions)
            elif "cronologia" in title_lower or "timeline" in title_lower:
                chart_bytes = ChartGenerator.timeline_milestones()
            elif "mapa" in title_lower or "força" in title_lower or "forca" in title_lower:
                chart_bytes = ChartGenerator.force_map()
            
            if chart_bytes:
                with open(chart_path, 'wb') as f:
                    f.write(chart_bytes)
                
                # Check if chart fits on current page
                if pdf.get_y() > 180:
                    pdf.add_page()
                
                pdf.image(chart_path, x=15, w=pdf.w - 30)
                os.unlink(chart_path)
                pdf.ln(6)
        
        except Exception as e:
            logger.warning(f"Erro ao renderizar gráfico para '{section_title}': {e}")
    
    @classmethod
    def _render_section_content(cls, pdf: AugurPDF, content: str):
        """Renderiza conteúdo markdown como texto formatado."""
        if not content:
            return
        
        # Clean markdown
        content = cls._clean_md(content)
        
        paragraphs = content.split('\n\n')
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Blockquote
            if para.startswith('>') or para.startswith('"'):
                cls._render_blockquote(pdf, para)
                continue
            
            # Bullet list
            if para.lstrip().startswith('- ') or para.lstrip().startswith('• '):
                cls._render_bullets(pdf, para)
                continue
            
            # Numbered list
            if re.match(r'^\d+[\.\)]\s', para.lstrip()):
                cls._render_bullets(pdf, para)
                continue
            
            # Regular paragraph (handle inline bold)
            cls._render_paragraph(pdf, para)
    
    @classmethod
    def _render_paragraph(cls, pdf: AugurPDF, text: str):
        """Parágrafo com suporte a **bold** inline."""
        # Check page space
        if pdf.get_y() > 260:
            pdf.add_page()
        
        # Remove ** and render as plain (fpdf2 limitation)
        clean = pdf._c(text.replace('**', ''))
        
        # Check if it looks like a sub-header (short, bold markers)
        if text.startswith('**') and text.endswith('**') and len(text) < 100:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*Colors.TEXT)
            pdf.ln(3)
            pdf.multi_cell(0, 6, clean)
            pdf.ln(2)
            return
        
        # Check if starts with bold (like "#N Name")
        if text.startswith('**') or re.match(r'^#\d+\s', text):
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*Colors.TEXT)
            pdf.ln(3)
            # Find end of bold part
            bold_end = text.find('**', 2)
            if bold_end > 0:
                bold_part = pdf._c(text[2:bold_end])
                rest = pdf._c(text[bold_end+2:].replace('**', ''))
                pdf.set_x(10)
                pdf.multi_cell(pdf.w - 20, 6, bold_part)
                if rest.strip():
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(60, 60, 80)
                    pdf.set_x(10)
                    pdf.multi_cell(pdf.w - 20, 5.5, rest)
            else:
                pdf.multi_cell(0, 6, clean)
            pdf.ln(2)
            return
        
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(60, 60, 80)
        pdf.multi_cell(0, 5.5, clean)
        pdf.ln(3)
    
    @classmethod
    def _render_blockquote(cls, pdf: AugurPDF, text: str):
        """Blockquote com barra lateral accent."""
        if pdf.get_y() > 255:
            pdf.add_page()
        
        clean = text.lstrip('> "').rstrip('"')
        clean = pdf._c(clean.replace('**', ''))
        
        # Save position
        x = pdf.get_x()
        y = pdf.get_y()
        
        # Quote bar
        pdf.set_fill_color(*Colors.ACCENT2)
        pdf.rect(12, y, 2, 0)  # Will adjust height after
        
        # Quote text
        pdf.set_x(18)
        pdf.set_font("Helvetica", "I", 8.5)
        pdf.set_text_color(80, 80, 110)
        
        start_y = pdf.get_y()
        pdf.multi_cell(pdf.w - 28, 5, f'"{clean}"')
        end_y = pdf.get_y()
        
        # Draw the bar with correct height
        pdf.set_fill_color(*Colors.ACCENT2)
        bar_height = max(end_y - start_y, 5)
        pdf.rect(12, start_y, 2, bar_height, "F")
        
        pdf.ln(4)
    
    @classmethod
    def _render_bullets(cls, pdf: AugurPDF, text: str):
        """Lista com bullets."""
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if pdf.get_y() > 270:
                pdf.add_page()
            
            # Remove bullet marker
            clean = re.sub(r'^[-•]\s*', '', line)
            clean = re.sub(r'^\d+[\.\)]\s*', '', clean)
            clean = pdf._c(clean.replace('**', ''))
            
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*Colors.ACCENT)
            pdf.cell(6, 5.5, "-")
            pdf.set_text_color(60, 60, 80)
            pdf.multi_cell(pdf.w - 26, 5.5, clean)
            pdf.ln(1)
        
        pdf.ln(2)
    
    @classmethod
    def _render_back_cover(cls, pdf: AugurPDF, verdict: str):
        """Contra-capa."""
        pdf.add_page()
        
        # Accent bars
        pdf.set_fill_color(*Colors.ACCENT)
        pdf.rect(0, 0, 6, 297, "F")
        pdf.set_fill_color(*Colors.ACCENT2)
        pdf.rect(0, 294, 210, 3, "F")
        
        # Verdict badge centered
        verdict_colors = {"GO": Colors.SUCCESS, "NO-GO": Colors.DANGER, "AJUSTAR": Colors.GOLD}
        badge_color = verdict_colors.get(verdict, Colors.GOLD)
        
        pdf.set_y(80)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*Colors.MUTED)
        pdf.cell(0, 8, pdf._c(f"{verdict} ANTES"), align="C", new_x="LMARGIN", new_y="NEXT")
        
        pdf.ln(3)
        
        # Summary line
        verdict_messages = {
            "GO": pdf._c("Sinal verde. Avance com as recomendações do relatório."),
            "NO-GO": pdf._c("Não recomendado neste formato. Revise a estratégia."),
            "AJUSTAR": pdf._c("Há espaço, mas exige ajustes antes de avançar."),
        }
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*Colors.MUTED)
        msg = verdict_messages.get(verdict, verdict_messages["AJUSTAR"])
        pdf.multi_cell(0, 6, msg, align="C")
        
        pdf.ln(30)
        
        # Logo
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(*Colors.TEXT)
        pdf.cell(0, 12, "AUGUR", align="C", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*Colors.MUTED)
        pdf.cell(0, 6, pdf._c("Preveja o futuro. Antes que ele aconteça."), 
                align="C", new_x="LMARGIN", new_y="NEXT")
        
        pdf.ln(15)
        
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(0, 5, "augur.itcast.com.br", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 5, "contato@itcast.com.br", align="C", new_x="LMARGIN", new_y="NEXT")
        
        pdf.ln(10)
        
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(180, 180, 200)
        pdf.multi_cell(0, 4.5, pdf._c(
            "Este relatório foi gerado por inteligência artificial. "
            "Os resultados representam cenários possíveis e não garantem resultados futuros."
        ), align="C")
    
    @staticmethod
    def _clean_md(text: str) -> str:
        """Remove formatação markdown pesada."""
        # Remove headers
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # Remove links
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        # Remove horizontal rules
        text = text.replace("---", "").replace("___", "")
        return text.strip()
