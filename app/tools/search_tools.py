from typing import Optional
from tavily import TavilyClient
from config.settings import settings


def web_search(query: str, max_results: int = 5, search_depth: str = "basic") -> dict:
    """Web検索を実行して結果を返す"""
    if not settings.tavily_api_key:
        return {"success": False, "error": "Tavily APIキーが設定されていません"}

    try:
        client = TavilyClient(api_key=settings.tavily_api_key)
        response = client.search(
            query=query,
            search_depth=search_depth,
            max_results=max_results,
            include_answer=True,
        )

        results = []
        for r in response.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:1000],
                "score": r.get("score", 0),
            })

        return {
            "success": True,
            "query": query,
            "answer": response.get("answer", ""),
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_webpage_content(url: str) -> dict:
    """特定のURLのコンテンツを取得"""
    if not settings.tavily_api_key:
        return {"success": False, "error": "Tavily APIキーが設定されていません"}

    try:
        client = TavilyClient(api_key=settings.tavily_api_key)
        response = client.extract(urls=[url])
        results = response.get("results", [])
        if results:
            return {
                "success": True,
                "url": url,
                "content": results[0].get("raw_content", "")[:5000],
            }
        return {"success": False, "error": "コンテンツを取得できませんでした"}
    except Exception as e:
        return {"success": False, "error": str(e)}
