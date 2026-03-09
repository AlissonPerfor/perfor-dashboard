"""
Meta Ads Analyzer - Ferramenta de Análise de Campanhas Meta Ads
================================================================
Conecta à Meta Marketing API e gera relatórios detalhados de performance.
"""

import os
import sys
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Tenta importar o SDK do Facebook
try:
    from facebook_business.api import FacebookAdsApi
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.campaign import Campaign
    from facebook_business.adobjects.adset import AdSet
    from facebook_business.adobjects.ad import Ad
    from facebook_business.adobjects.adsinsights import AdsInsights
except ImportError:
    print("❌ SDK do Facebook não encontrado. Instale com:")
    print("   pip install facebook-business")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
except ImportError:
    print("❌ Rich não encontrado. Instale com:")
    print("   pip install rich")
    sys.exit(1)

console = Console()


def init_api():
    """Inicializa a conexão com a Meta Marketing API."""
    access_token = os.getenv("META_ACCESS_TOKEN")
    ad_account_id = os.getenv("META_AD_ACCOUNT_ID")

    if not access_token or not ad_account_id:
        console.print("[bold red]❌ Credenciais não encontradas![/]")
        console.print("Configure o arquivo .env com META_ACCESS_TOKEN e META_AD_ACCOUNT_ID")
        sys.exit(1)

    FacebookAdsApi.init(access_token=access_token)
    return AdAccount(ad_account_id)


def format_currency(value):
    """Formata valores monetários."""
    try:
        return f"R$ {float(value):,.2f}"
    except (ValueError, TypeError):
        return "R$ 0,00"


def format_number(value):
    """Formata números com separador de milhar."""
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return "0"


def format_percentage(value):
    """Formata valores percentuais."""
    try:
        return f"{float(value):.2f}%"
    except (ValueError, TypeError):
        return "0.00%"


def get_account_info(account):
    """Busca informações da conta de anúncios."""
    console.print("\n[bold cyan]🔍 Buscando informações da conta...[/]\n")

    fields = [
        'name',
        'account_status',
        'currency',
        'balance',
        'amount_spent',
        'business_name',
        'timezone_name',
    ]

    try:
        info = account.api_get(fields=fields)

        status_map = {
            1: "✅ Ativa",
            2: "❌ Desativada",
            3: "⚠️ Não Segura",
            7: "⏸️ Pendente",
            8: "⏸️ Revisão Pendente",
            9: "🔒 Em Período de Carência",
            100: "⏸️ Análise Pendente",
            101: "🔒TemporariamenteeIndisponível",
        }

        table = Table(
            title="📋 Informações da Conta",
            box=box.ROUNDED,
            show_header=False,
            title_style="bold magenta",
            border_style="cyan",
            padding=(0, 2),
        )
        table.add_column("Campo", style="bold yellow", width=25)
        table.add_column("Valor", style="white")

        table.add_row("Nome da Conta", str(info.get('name', 'N/A')))
        table.add_row("Empresa", str(info.get('business_name', 'N/A')))
        table.add_row("Status", status_map.get(info.get('account_status', 0), 'Desconhecido'))
        table.add_row("Moeda", str(info.get('currency', 'N/A')))
        table.add_row("Fuso Horário", str(info.get('timezone_name', 'N/A')))
        table.add_row("Saldo", format_currency(info.get('balance', 0)))
        table.add_row("Total Gasto", format_currency(info.get('amount_spent', 0)))

        console.print(table)
        return info

    except Exception as e:
        console.print(f"[bold red]❌ Erro ao buscar informações da conta: {e}[/]")
        return None


def get_campaigns(account):
    """Busca todas as campanhas da conta."""
    console.print("\n[bold cyan]📊 Buscando campanhas...[/]\n")

    fields = [
        'name',
        'status',
        'objective',
        'daily_budget',
        'lifetime_budget',
        'start_time',
        'stop_time',
        'created_time',
        'updated_time',
    ]

    params = {
        'limit': 100,
    }

    try:
        campaigns = account.get_campaigns(fields=fields, params=params)

        if not campaigns:
            console.print("[yellow]⚠️ Nenhuma campanha encontrada na conta.[/]")
            return []

        table = Table(
            title=f"🚀 Campanhas ({len(campaigns)} encontradas)",
            box=box.ROUNDED,
            title_style="bold magenta",
            border_style="cyan",
            padding=(0, 1),
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("Nome", style="bold white", max_width=35)
        table.add_column("Status", width=12)
        table.add_column("Objetivo", style="cyan", width=20)
        table.add_column("Orçamento Diário", style="green", justify="right", width=16)
        table.add_column("Criada em", style="dim", width=12)

        status_styles = {
            'ACTIVE': '[bold green]✅ Ativa[/]',
            'PAUSED': '[yellow]⏸️ Pausada[/]',
            'DELETED': '[red]🗑️ Deletada[/]',
            'ARCHIVED': '[dim]📦 Arquivada[/]',
        }

        for i, camp in enumerate(campaigns, 1):
            status = camp.get('status', 'UNKNOWN')
            daily_budget = camp.get('daily_budget')
            budget_str = format_currency(float(daily_budget) / 100) if daily_budget else "—"

            created = camp.get('created_time', '')
            if created:
                try:
                    created = datetime.fromisoformat(created.replace('+0000', '+00:00')).strftime('%d/%m/%Y')
                except:
                    created = created[:10]

            table.add_row(
                str(i),
                str(camp.get('name', 'N/A'))[:35],
                status_styles.get(status, status),
                str(camp.get('objective', 'N/A')),
                budget_str,
                created,
            )

        console.print(table)
        return campaigns

    except Exception as e:
        console.print(f"[bold red]❌ Erro ao buscar campanhas: {e}[/]")
        return []


def get_campaign_insights(account, date_preset='last_30d'):
    """Busca insights de performance das campanhas."""
    console.print(f"\n[bold cyan]📈 Buscando insights de performance (últimos 30 dias)...[/]\n")

    fields = [
        'campaign_name',
        'campaign_id',
        'impressions',
        'clicks',
        'spend',
        'reach',
        'cpc',
        'cpm',
        'ctr',
        'actions',
        'action_values',
        'cost_per_action_type',
        'frequency',
        'conversions',
        'cost_per_conversion',
        'purchase_roas',
    ]

    params = {
        'level': 'campaign',
        'date_preset': date_preset,
        'limit': 100,
    }

    try:
        insights = account.get_insights(fields=fields, params=params)
        insights_list = list(insights)

        if not insights_list:
            console.print("[yellow]⚠️ Nenhum dado de performance encontrado para o período.[/]")
            return []

        # Tabela de Performance
        table = Table(
            title="📊 Performance das Campanhas (Últimos 30 dias)",
            box=box.ROUNDED,
            title_style="bold magenta",
            border_style="cyan",
            padding=(0, 1),
        )
        table.add_column("Campanha", style="bold white", max_width=25)
        table.add_column("Impressões", style="cyan", justify="right")
        table.add_column("Cliques", style="green", justify="right")
        table.add_column("CTR", style="yellow", justify="right")
        table.add_column("Gasto", style="bold green", justify="right")
        table.add_column("Compras", style="bold magenta", justify="right")
        table.add_column("CPA", style="red", justify="right")
        table.add_column("Vlr Conv.", style="bold cyan", justify="right")
        table.add_column("ROAS", style="bold yellow", justify="right")

        total_impressions = 0
        total_clicks = 0
        total_spend = 0.0
        total_reach = 0
        total_purchases = 0
        total_conversion_value = 0.0

        for insight in insights_list:
            impressions = int(insight.get('impressions', 0))
            clicks = int(insight.get('clicks', 0))
            spend = float(insight.get('spend', 0))
            reach = int(insight.get('reach', 0))

            # Extrair compras das actions
            purchases = 0
            actions = insight.get('actions', [])
            if actions:
                for action in actions:
                    if action.get('action_type') == 'purchase':
                        purchases = int(action.get('value', 0))
                        break

            # Extrair valor de conversão de compras
            conversion_value = 0.0
            action_values = insight.get('action_values', [])
            if action_values:
                for av in action_values:
                    if av.get('action_type') == 'purchase':
                        conversion_value = float(av.get('value', 0))
                        break

            # Extrair CPA (custo por compra)
            cpa = 0.0
            cost_per_actions = insight.get('cost_per_action_type', [])
            if cost_per_actions:
                for cpa_item in cost_per_actions:
                    if cpa_item.get('action_type') == 'purchase':
                        cpa = float(cpa_item.get('value', 0))
                        break

            # Extrair ROAS
            roas = 0.0
            purchase_roas = insight.get('purchase_roas', [])
            if purchase_roas:
                for roas_item in purchase_roas:
                    if roas_item.get('action_type') == 'omni_purchase':
                        roas = float(roas_item.get('value', 0))
                        break

            total_impressions += impressions
            total_clicks += clicks
            total_spend += spend
            total_reach += reach
            total_purchases += purchases
            total_conversion_value += conversion_value

            table.add_row(
                str(insight.get('campaign_name', 'N/A'))[:25],
                format_number(impressions),
                format_number(clicks),
                format_percentage(insight.get('ctr', 0)),
                format_currency(spend),
                format_number(purchases) if purchases > 0 else "—",
                format_currency(cpa) if cpa > 0 else "—",
                format_currency(conversion_value) if conversion_value > 0 else "—",
                f"{roas:.2f}x" if roas > 0 else "—",
            )

        # Linha de totais
        avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        avg_cpc = (total_spend / total_clicks) if total_clicks > 0 else 0
        avg_cpm = (total_spend / total_impressions * 1000) if total_impressions > 0 else 0
        total_cpa = (total_spend / total_purchases) if total_purchases > 0 else 0
        total_roas = (total_conversion_value / total_spend) if total_spend > 0 else 0

        table.add_section()
        table.add_row(
            "[bold]TOTAL[/]",
            f"[bold]{format_number(total_impressions)}[/]",
            f"[bold]{format_number(total_clicks)}[/]",
            f"[bold]{format_percentage(avg_ctr)}[/]",
            f"[bold]{format_currency(total_spend)}[/]",
            f"[bold]{format_number(total_purchases)}[/]" if total_purchases > 0 else "—",
            f"[bold]{format_currency(total_cpa)}[/]" if total_cpa > 0 else "—",
            f"[bold]{format_currency(total_conversion_value)}[/]" if total_conversion_value > 0 else "—",
            f"[bold]{total_roas:.2f}x[/]" if total_roas > 0 else "—",
        )

        console.print(table)

        # Painel de resumo
        summary = Table(
            title="📋 Resumo Geral",
            box=box.ROUNDED,
            title_style="bold magenta",
            border_style="green",
            show_header=False,
            padding=(0, 2),
        )
        summary.add_column("Métrica", style="bold yellow", width=30)
        summary.add_column("Valor", style="bold white", justify="right")

        summary.add_row("Total Investido", format_currency(total_spend))
        summary.add_row("Total de Impressões", format_number(total_impressions))
        summary.add_row("Total de Alcance (pessoas)", format_number(total_reach))
        summary.add_row("Total de Cliques", format_number(total_clicks))
        summary.add_row("CTR Médio", format_percentage(avg_ctr))
        summary.add_row("CPC Médio", format_currency(avg_cpc))
        summary.add_row("CPM Médio", format_currency(avg_cpm))
        summary.add_row("Campanhas Ativas", str(len(insights_list)))

        console.print()
        console.print(summary)

        # Painel de Métricas de Conversão
        conv_table = Table(
            title="🛒 Métricas de Conversão (Compras)",
            box=box.ROUNDED,
            title_style="bold magenta",
            border_style="yellow",
            show_header=False,
            padding=(0, 2),
        )
        conv_table.add_column("Métrica", style="bold yellow", width=35)
        conv_table.add_column("Valor", style="bold white", justify="right")

        conv_table.add_row("🛒 Total de Compras (Purchases)", format_number(total_purchases) if total_purchases > 0 else "Nenhuma")
        conv_table.add_row("💰 Valor Total de Conversão", format_currency(total_conversion_value) if total_conversion_value > 0 else "—")
        conv_table.add_row("💸 CPA (Custo por Compra)", format_currency(total_cpa) if total_cpa > 0 else "—")
        conv_table.add_row("📈 ROAS Geral (Purchase ROAS)", f"{total_roas:.2f}x" if total_roas > 0 else "—")
        conv_table.add_row("💵 Ticket Médio", format_currency(total_conversion_value / total_purchases) if total_purchases > 0 else "—")
        conv_table.add_row("📊 Lucro/Prejuízo Estimado", format_currency(total_conversion_value - total_spend) if total_conversion_value > 0 else "—")

        console.print()
        console.print(conv_table)



        # Análise de ações/conversões
        show_actions(insights_list)

        return insights_list

    except Exception as e:
        console.print(f"[bold red]❌ Erro ao buscar insights: {e}[/]")
        import traceback
        traceback.print_exc()
        return []


def show_actions(insights_list):
    """Mostra detalhes de ações (conversões, leads, etc)."""
    all_actions = {}

    for insight in insights_list:
        actions = insight.get('actions', [])
        if actions:
            for action in actions:
                action_type = action.get('action_type', 'unknown')
                value = int(action.get('value', 0))
                all_actions[action_type] = all_actions.get(action_type, 0) + value

    if all_actions:
        table = Table(
            title="🎯 Ações e Conversões (Todas as Campanhas)",
            box=box.ROUNDED,
            title_style="bold magenta",
            border_style="yellow",
            padding=(0, 2),
        )
        table.add_column("Tipo de Ação", style="bold white", width=40)
        table.add_column("Quantidade", style="green", justify="right")

        action_labels = {
            'link_click': '🔗 Cliques no Link',
            'post_engagement': '💬 Engajamento no Post',
            'page_engagement': '📄 Engajamento na Página',
            'post_reaction': '❤️ Reações',
            'comment': '💬 Comentários',
            'like': '👍 Curtidas',
            'share': '🔄 Compartilhamentos',
            'video_view': '🎬 Visualizações de Vídeo',
            'photo_view': '📷 Visualizações de Foto',
            'landing_page_view': '🌐 Views da Landing Page',
            'onsite_conversion.messaging_conversation_started_7d': '💬 Conversas Iniciadas',
            'onsite_conversion.lead_grouped': '📋 Leads',
            'lead': '📋 Leads',
            'purchase': '🛒 Compras',
            'add_to_cart': '🛒 Adições ao Carrinho',
            'initiate_checkout': '💳 Checkouts Iniciados',
            'complete_registration': '📝 Registros Completos',
        }

        sorted_actions = sorted(all_actions.items(), key=lambda x: x[1], reverse=True)

        for action_type, value in sorted_actions:
            label = action_labels.get(action_type, f"📌 {action_type}")
            table.add_row(label, format_number(value))

        console.print()
        console.print(table)


def get_daily_breakdown(account, days=7):
    """Busca breakdown diário da performance."""
    console.print(f"\n[bold cyan]📅 Performance diária (últimos {days} dias)...[/]\n")

    fields = [
        'impressions',
        'clicks',
        'spend',
        'reach',
        'ctr',
        'cpc',
    ]

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    params = {
        'time_range': {
            'since': start_date.strftime('%Y-%m-%d'),
            'until': end_date.strftime('%Y-%m-%d'),
        },
        'time_increment': 1,
        'limit': 100,
    }

    try:
        insights = account.get_insights(fields=fields, params=params)
        insights_list = list(insights)

        if not insights_list:
            console.print("[yellow]⚠️ Nenhum dado diário encontrado.[/]")
            return

        table = Table(
            title=f"📅 Performance Diária ({days} dias)",
            box=box.ROUNDED,
            title_style="bold magenta",
            border_style="cyan",
            padding=(0, 1),
        )
        table.add_column("Data", style="bold white", width=12)
        table.add_column("Impressões", style="cyan", justify="right")
        table.add_column("Alcance", style="blue", justify="right")
        table.add_column("Cliques", style="green", justify="right")
        table.add_column("CTR", style="yellow", justify="right")
        table.add_column("CPC", style="red", justify="right")
        table.add_column("Gasto", style="bold green", justify="right")

        for insight in insights_list:
            date_str = insight.get('date_start', 'N/A')
            try:
                date_str = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')
            except:
                pass

            table.add_row(
                date_str,
                format_number(insight.get('impressions', 0)),
                format_number(insight.get('reach', 0)),
                format_number(insight.get('clicks', 0)),
                format_percentage(insight.get('ctr', 0)),
                format_currency(insight.get('cpc', 0)),
                format_currency(insight.get('spend', 0)),
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]❌ Erro ao buscar dados diários: {e}[/]")


def get_demographic_breakdown(account):
    """Busca breakdown demográfico (idade e gênero)."""
    console.print("\n[bold cyan]👥 Análise demográfica (últimos 30 dias)...[/]\n")

    fields = [
        'impressions',
        'clicks',
        'spend',
        'reach',
        'ctr',
    ]

    params = {
        'date_preset': 'last_30d',
        'breakdowns': ['age', 'gender'],
        'limit': 100,
    }

    try:
        insights = account.get_insights(fields=fields, params=params)
        insights_list = list(insights)

        if not insights_list:
            console.print("[yellow]⚠️ Nenhum dado demográfico encontrado.[/]")
            return

        table = Table(
            title="👥 Performance por Idade e Gênero",
            box=box.ROUNDED,
            title_style="bold magenta",
            border_style="cyan",
            padding=(0, 1),
        )
        table.add_column("Idade", style="bold white", width=10)
        table.add_column("Gênero", style="cyan", width=12)
        table.add_column("Impressões", style="blue", justify="right")
        table.add_column("Alcance", style="blue", justify="right")
        table.add_column("Cliques", style="green", justify="right")
        table.add_column("CTR", style="yellow", justify="right")
        table.add_column("Gasto", style="bold green", justify="right")

        gender_map = {
            'male': '👨 Masculino',
            'female': '👩 Feminino',
            'unknown': '❓ Outros',
        }

        sorted_insights = sorted(insights_list, key=lambda x: float(x.get('spend', 0)), reverse=True)

        for insight in sorted_insights:
            table.add_row(
                str(insight.get('age', 'N/A')),
                gender_map.get(insight.get('gender', ''), insight.get('gender', 'N/A')),
                format_number(insight.get('impressions', 0)),
                format_number(insight.get('reach', 0)),
                format_number(insight.get('clicks', 0)),
                format_percentage(insight.get('ctr', 0)),
                format_currency(insight.get('spend', 0)),
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]❌ Erro ao buscar dados demográficos: {e}[/]")


def get_placement_breakdown(account):
    """Busca breakdown por posicionamento (Feed, Stories, Reels, etc)."""
    console.print("\n[bold cyan]📱 Análise por posicionamento (últimos 30 dias)...[/]\n")

    fields = [
        'impressions',
        'clicks',
        'spend',
        'reach',
        'ctr',
        'cpc',
    ]

    params = {
        'date_preset': 'last_30d',
        'breakdowns': ['publisher_platform', 'platform_position'],
        'limit': 100,
    }

    try:
        insights = account.get_insights(fields=fields, params=params)
        insights_list = list(insights)

        if not insights_list:
            console.print("[yellow]⚠️ Nenhum dado de posicionamento encontrado.[/]")
            return

        table = Table(
            title="📱 Performance por Posicionamento",
            box=box.ROUNDED,
            title_style="bold magenta",
            border_style="cyan",
            padding=(0, 1),
        )
        table.add_column("Plataforma", style="bold white", width=14)
        table.add_column("Posição", style="cyan", width=22)
        table.add_column("Impressões", style="blue", justify="right")
        table.add_column("Cliques", style="green", justify="right")
        table.add_column("CTR", style="yellow", justify="right")
        table.add_column("CPC", style="red", justify="right")
        table.add_column("Gasto", style="bold green", justify="right")

        platform_map = {
            'facebook': '📘 Facebook',
            'instagram': '📸 Instagram',
            'messenger': '💬 Messenger',
            'audience_network': '🌐 Audience Net',
        }

        sorted_insights = sorted(insights_list, key=lambda x: float(x.get('spend', 0)), reverse=True)

        for insight in sorted_insights:
            platform = insight.get('publisher_platform', 'N/A')
            position = insight.get('platform_position', 'N/A')

            table.add_row(
                platform_map.get(platform, platform),
                position.replace('_', ' ').title(),
                format_number(insight.get('impressions', 0)),
                format_number(insight.get('clicks', 0)),
                format_percentage(insight.get('ctr', 0)),
                format_currency(insight.get('cpc', 0)),
                format_currency(insight.get('spend', 0)),
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]❌ Erro ao buscar dados de posicionamento: {e}[/]")


def main():
    """Função principal - executa análise completa."""
    console.print(Panel(
        Text("META ADS ANALYZER", style="bold white", justify="center"),
        subtitle="Análise Completa de Campanhas",
        border_style="bright_blue",
        padding=(1, 2),
    ))

    console.print("[dim]Conectando à Meta Marketing API...[/]\n")

    # Inicializa API
    account = init_api()

    # 1. Informações da conta
    get_account_info(account)

    # 2. Lista de campanhas
    campaigns = get_campaigns(account)

    # 3. Insights de performance
    insights = get_campaign_insights(account)

    # 4. Performance diária
    get_daily_breakdown(account, days=7)

    # 5. Análise demográfica
    get_demographic_breakdown(account)

    # 6. Análise por posicionamento
    get_placement_breakdown(account)

    # Finalização
    console.print()
    console.print(Panel(
        "[bold green]✅ Análise completa finalizada![/]\n\n"
        "Os dados acima mostram o panorama geral das suas campanhas Meta Ads.\n"
        "Para mais detalhes, você pode executar novamente com filtros específicos.",
        title="🎉 Concluído",
        border_style="green",
        padding=(1, 2),
    ))


if __name__ == "__main__":
    main()
