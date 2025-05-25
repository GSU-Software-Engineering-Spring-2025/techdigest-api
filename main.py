from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from eventregistry import EventRegistry, QueryArticlesIter
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["GET"],
    allow_headers=["*"],
    allow_credentials=True
)

@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize EventRegistry client
er = EventRegistry(apiKey=os.getenv("EVENT_REGISTRY_KEY"))

# Define date range - last 2 years (730 days)
forceMaxDataTimeWindow = "730"

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/api/articles")
async def getArticles():
    try:
        query = {
            "$query": {
                "$and": [
                    {
                        "$or": [
                            {
                                "keyword": "AI",
                                "keywordLoc": "body" 
                            },
                            {
                                "keyword": "technology",
                                "keywordLoc": "body"
                            },
                            {
                                "conceptUri": "http://en.wikipedia.org/wiki/Technology"
                            }
                        ]
                    },
                    {
                        "lang": "eng"
                    }
                ]
            },
            "$filter": {
                "forceMaxDataTimeWindow": forceMaxDataTimeWindow,
                "startSourceRankPercentile": 0,
                "endSourceRankPercentile": 20 
            }
        }
        
        q = QueryArticlesIter.initWithComplexQuery(query)
        articles_list = list(q.execQuery(er, maxItems=25))
        
        logger.info(f"Retrieved {len(articles_list)} general articles")
        return parse_articles(articles_list)
    except Exception as e:
        logger.error(f"Error retrieving articles: {str(e)}")
        return []

# Dictionary with simplified queries for different categories
CATEGORY_QUERIES = {
    "ai": {
        "keywords": ["AI", "artificial intelligence", "machine learning", "GPT"],
        "concepts": ["http://en.wikipedia.org/wiki/Artificial_intelligence"],
        "category": "AI"
    },
    "machine learning": {
        "keywords": ["machine learning", "ML", "data science"],
        "concepts": ["http://en.wikipedia.org/wiki/Machine_Learning"],
        "category": "ML"
    },
    "iot": {
        "keywords": ["IoT", "Internet of Things", "connected devices"],
        "concepts": ["http://en.wikipedia.org/wiki/Internet_of_things"],
        "category": "IoT"
    },
    "blockchain": {
        "keywords": ["blockchain", "cryptocurrency", "Bitcoin", "Ethereum"],
        "concepts": ["http://en.wikipedia.org/wiki/Blockchain"],
        "category": "Blockchain"
    },
    "quantum computing": {
        "keywords": ["quantum computing", "quantum computer"],
        "concepts": ["http://en.wikipedia.org/wiki/Quantum_computing"],
        "category": "Quantum Computing"
    },
    "virtual reality": {
        "keywords": ["VR", "virtual reality", "augmented reality", "AR", "metaverse"],
        "concepts": ["http://en.wikipedia.org/wiki/Virtual_reality"],
        "category": "VR"
    },
    "cybersecurity": {
        "keywords": ["cybersecurity", "data breach", "hacking"],
        "concepts": ["http://en.wikipedia.org/wiki/Computer_security"],
        "category": "Networking"
    },
    "robotics": {
        "keywords": ["robotics", "robot", "automation"],
        "concepts": ["http://en.wikipedia.org/wiki/Robotics"],
        "category": "Robotics"
    }
}

def parse_articles(articles_list):
    parsed_articles = []

    for article in articles_list:
        # Skip duplicates
        if article.get("isDuplicate"):
            continue
            
        # Extract author names
        authors = article.get("authors", [])
        author_names = [author.get("name", "Unknown") for author in authors]
        
        # Extract categories
        categories = article.get("categories", [])
        category_names = [category.get("label", "Unknown") for category in categories]
        
        # Create a summary if body exists
        summary = ""
        if article.get("body"):
            # Create a summary of up to 200 characters
            summary = article.get("body", "")[:200]
            if len(article.get("body", "")) > 200:
                summary += "..."
                
        # Use a default image if none exists
        image = article.get("image") if article.get("image") else "/placeholder.png"
        
        parsed_articles.append({
            "source": article.get("source", {}).get("title", "Unknown Source"),
            "authors": ", ".join(author_names) if author_names else "Unknown Author",
            "title": article.get("title", ""),
            "summary": article.get("description", summary),
            "id": article.get("uri", ""),
            "url": article.get("url", ""),
            "image": image,
            "date": article.get("dateTime", article.get("date", "")),
            "body": article.get("body", "No content available"),
            "category": ", ".join(category_names) if category_names else "Tech" 
        })
    
    return parsed_articles

async def getArticlesByCat(category):
    try:
        # Get enhanced query parameters for this category
        category_info = CATEGORY_QUERIES.get(category, {
            "keywords": [category],
            "concepts": [],
            "category": "Tech"
        })
        
        keywords = category_info["keywords"]
        concepts = category_info["concepts"]
        display_category = category_info["category"]
        
        keyword_conditions = []
        for keyword in keywords:
            keyword_conditions.append({
                "keyword": keyword,
                "keywordLoc": "body"
            })
        
        concept_conditions = []
        for concept in concepts:
            concept_conditions.append({
                "conceptUri": concept
            })
        
        or_conditions = []
        if keyword_conditions:
            or_conditions.append({
                "$or": keyword_conditions
            })
        if concept_conditions:
            or_conditions.append({
                "$or": concept_conditions
            })
        
        query = {
            "$query": {
                "$and": [
                    {
                        "$or": or_conditions
                    },
                    {
                        "lang": "eng"
                    }
                ]
            },
            "$filter": {
                "forceMaxDataTimeWindow": forceMaxDataTimeWindow,
                "startSourceRankPercentile": 0,
                "endSourceRankPercentile": 60 
            }
        }
        
        logger.info(f"Executing query for category: {category}")
        q = QueryArticlesIter.initWithComplexQuery(query)
        articles_list = list(q.execQuery(er, maxItems=25))
        
        parsed_articles = []
        for article in parse_articles(articles_list):
            # Override the category with our defined category
            article["category"] = display_category
            parsed_articles.append(article)
            
        logger.info(f"Retrieved {len(parsed_articles)} articles for category {category}")
        return parsed_articles
    except Exception as e:
        logger.error(f"Error retrieving articles for category {category}: {str(e)}")
        return []

@app.get("/api/articles/AI")
async def getArticlesAI():
    return await getArticlesByCat("ai")

@app.get("/api/articles/ML")
async def getArticlesML():
    return await getArticlesByCat("machine learning")

@app.get("/api/articles/IoT")
async def getArticlesIOT():
    return await getArticlesByCat("internet of things")

@app.get("/api/articles/Blockchain")
async def getArticlesBlockchain():
    return await getArticlesByCat("blockchain")

@app.get("/api/articles/Quantum Computing")
async def getArticlesQuantumComputing():
    return await getArticlesByCat("quantum computing")

@app.get("/api/articles/VR/AR")
async def getArticlesVirtualReality():
    return await getArticlesByCat("virtual reality")

@app.get("/api/articles/Networking")
async def getArticlesCybersecurity():
    return await getArticlesByCat("networking")

@app.get("/api/articles/Robotics")
async def getArticlesRobotics():
    return await getArticlesByCat("robotics")

# Add a trending tech endpoint with simplified query
@app.get("/api/articles/trending")
async def getTrendingTech():
    try:
        # Simplified query for recent tech news
        query = {
            "$query": {
                "$and": [
                    {
                        "$or": [
                            {
                                "keyword": "tech",
                                "keywordLoc": "body"
                            },
                            {
                                "keyword": "technology",
                                "keywordLoc": "body"
                            },
                            {
                                "conceptUri": "http://en.wikipedia.org/wiki/Technology"
                            }
                        ]
                    },
                    {
                        "lang": "eng"
                    }
                ]
            },
            "$filter": {
                "forceMaxDataTimeWindow": "120", 
                "startSourceRankPercentile": 0,
                "endSourceRankPercentile": 30 
            }
        }
        
        q = QueryArticlesIter.initWithComplexQuery(query)
        articles_list = list(q.execQuery(er, maxItems=25))
        
        parsed_articles = []
        for article in parse_articles(articles_list):
            article["category"] = "Trending"
            parsed_articles.append(article)
            
        logger.info(f"Retrieved {len(parsed_articles)} trending articles")
        return parsed_articles
    except Exception as e:
        logger.error(f"Error retrieving trending articles: {str(e)}")
        return []

port = int(os.environ.get("PORT", 8000))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
