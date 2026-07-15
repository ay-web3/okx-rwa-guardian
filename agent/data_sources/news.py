import logging
import httpx
import urllib.parse
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

async def fetch_news_alerts(prop_id: str, asset_name: str = None):
    """
    Fetches real news alerts regarding regulatory or economic threats using Google News RSS.
    """
    if asset_name:
        query = f'"{asset_name}" when:14d'
    else:
        queries = {
            "miami": "Miami Real Estate OR Florida housing market",
            "tokyo": "Tokyo Commercial Real Estate OR Japan economy",
            "texas": "Austin Real Estate OR Texas tech housing"
        }
        query = queries.get(prop_id, "Real Estate Market")
        
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}"
    
    alerts = []
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url)
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                # Parse the top 2 news items
                for item in root.findall('.//item')[:2]:
                    title = item.find('title').text
                    pub_date = item.find('pubDate').text
                    alerts.append({
                        "id": "real_news_01",
                        "type": "market_news",
                        "source": "Google News API",
                        "headline": title,
                        "severity": "LOW",
                        "description": f"Routine market news published on {pub_date}. Unless this explicitly mentions a catastrophic crash, disaster, or severe regulatory ban, do not pause trading.",
                        "timestamp": pub_date
                    })
    except Exception as e:
        logger.error(f"Failed to fetch real news for {prop_id}: {e}")
        
    return alerts

def simulate_news_event(prop_id: str, headline: str, severity: str):
    """
    Returns a mocked news object (still used for manual frontend testing buttons).
    """
    return {
        "id": "news_sim_01",
        "type": "regulatory_news",
        "source": "GNews API",
        "headline": headline,
        "severity": severity,
        "description": f"Breaking news: {headline}. This could severely impact short-term rental yields in the area.",
        "timestamp": "Just now"
    }
