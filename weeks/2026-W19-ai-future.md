---
title: "Growth Week 2026-W19 — Modern Retrieval and RAG"
author: "Personal Growth Assistant"
subtitle: "ai-future · modern-retrieval-and-rag"
lang: en
---

# Growth Week 2026-W19

**Focus:** modern retrieval and RAG. Sparse vs dense retrieval, BM25, hybrid pipelines, and why the "embed query, search vectors" pattern fails in production.

You've shipped RAG with Graphiti and gotten great results without knowing what was happening below the API. This week pulls that layer up. By the end you should be able to explain — to a peer or to yourself, in your own words — what BM25 scores, what dense embeddings score, why neither alone is enough, and what reranking adds. That's the floor. Future weeks can go deeper on any one of these.

Five sources, ordered: foundational intuition (Yan), why naive RAG breaks (Liu), a concrete hybrid implementation (Yan), a current production case where literal grep beat embeddings (Liu), and a practitioner playbook for systematic RAG improvement (Liu). No papers this week — calibrated for getting comfortable with the concepts, not for arguing with researchers.

<!-- targeted ~21k–32k words; came in around ~13k. At confidence 1 with new conceptual material, real reading speed is closer to 130 wpm than 220 — estimated read time ~90 min. If too short, signal in EOW review and next week will pack more. -->

---

## Search: Query Matching via Lexical, Graph, and Embedding Methods

*Eugene Yan · eugeneyan.com · 25 April 2021 · [https://eugeneyan.com/writing/search-query-matching/](https://eugeneyan.com/writing/search-query-matching/)*

> Pre-LLM but the foundation under everything you're shipping today. The vocabulary you're missing — *lexical*, *embedding-based*, *query expansion*, *bipartite click graph* — is built up here from concrete e-commerce examples (DoorDash, Yahoo, Uber Eats). As you read, hold this question in your head: **what failure mode does each approach exist to solve?** Skim the graph section quickly; it's adjacent to your existing GraphRAG instinct. Spend your attention on lexical and embedding.

Search and recommendations have a lot in common. They help users learn about new products, and need to retrieve and rank millions of products in a very short time (<150ms). They’re trained on similar data, have content and behavioral-based approaches, and optimize for engagement (e.g., click-through rate) and revenue (e.g., conversion, gross merchandise value).

**Nonetheless, search differs in one key aspect—it has the user’s query as additional input.** (Think of search as recommendations with the query as extra context.) This is a boon and a bane. It’s a boon because the query provides more context to help us help users find what they want; it’s a bane because users expect results to be in line with their query.

In this post, we’ll explore various ways to normalize, rewrite, and retrieve (aka match) documents using **the query**. (Though the ranking step is also important, we’ll focus on query processing and matching for now). We’ll compare three main approaches:

* **Lexical-based**: This approach replaces or augments the query string directly via normalization, spellchecks, expansion, translation, etc.
* **Graph-based**: This uses a knowledge graph is used to understand queries and documents at a higher level for query expansion and matching.
* **Embedding-based**: This uses latent representations—learned via self-supervised or supervised techniques—for expansion and matching.

## Lexical-based: The bedrock of query processing

Lexical-based approaches start with **preprocessing** the query string. This includes normalization (e.g., stemming, unicode standardization, removing accents), spell checking, and tokenization. Stemming in particular helps to reduce the various morphological forms of words to the same query. For example, “hiking boot” and “hike boots” are [stemmed](https://9ol.es/porter_js_demo.html) to “hike boot”, making it easier for downstream matching of queries to documents. In general, these preprocessing steps replace the query.

**Query expansion** augments the query by adding tokens to match additional documents. Additional tokens include synonyms (e.g., “handphone” can be expanded to “handphone OR mobile phone OR cellphone”) and abbreviations (e.g., “t-shirt L” can be expanded to “t-shirt L OR t-shirt large”).

**Query relaxation** is somewhat the opposite of query expansion; we remove tokens from the query instead. This makes the query less restrictive and increases recall. The simplest approach is to remove stop words. For product search, query relaxation can drop color, measure (e.g., small, medium, large), model numbers, brand, and other entities.

For example, “acme gold iphone charger i012e large” can be relaxed to “iphone charger”. Trying to match on the full query string leads to no results. But in this case, we can infer that the key intent is “iphone charger” and relax the query string to increase recall. The example below also shows “charger” being rewritten to “charging”, as well as query expansion by adding the “apple” token.

![An example of query rewriting, relaxation, and expansion](https://eugeneyan.com/assets/query-processing.webp "An example of query rewriting, relaxation, and expansion")

An example of query rewriting, relaxation, and expansion

**Query translation** is another form of rewriting, where a text-translation paradigm is applied to convert tail (i.e., unpopular, 20th percentile) queries into head queries that account for the bulk of traffic, helping to increase recall. It also helps in downstream ranking as we have more behavioral information (e.g., clicks, purchases) on head queries.

After the query is processed, it can be used to **retrieve relevant documents**. For lexical approaches, it mostly involves matching tokens and n-grams in the query to document fields such as title, description, category, attributes, etc.

**[DoorDash’s search system](https://doordash.engineering/2020/12/15/understanding-search-intent-with-better-recall/) starts with basic processing** (e.g., removing extra whitespaces, lowercasing, expanding contractions) before spell correction via the [Symmetric Delete](https://github.com/wolfgarbe/SymSpell) spelling correction algorithm. Then, the updated query tokens are standardized via a manually curated synonym dictionary. For example, “Poulet Frit Kentucky”, “KFZ”, and “KFC” are normalized to “kfc”.

However, specific—and valid—queries such as “Chick’n” were being spell-corrected to “Chicken”. (There are many items in their catalog with names that might not be present in an English dictionary and have low edit distance to regular words.) To avoid these invalid corrections, they apply spell check only after the initial attempt at matching does not return any results.

![My spellchecker wanted to replace Chick'n too](https://eugeneyan.com/assets/chicken-spellcheck.webp "My spellchecker wanted to replace Chick'n too")

My spellchecker wanted to replace "Chick'n" too

**[Yahoo shared about their text-translation approach](https://www.kdd.org/kdd2016/subtopic/view/ranking-relevance-in-yahoo-search)** to rewrite queries. The intent was to overcome the problem of matching and ranking cold start queries (not seen in the click log). To achieve this, they built a translation model using query-document pairs from their bipartite click graph. (A bipartite graph is a graph where nodes can be separated into two, disjointed sets, such as queries and documents.) The translation model learns phrase-level translations such as word alignment, phrase extraction, and phrase scoring. At query time, the model segments each query into phrases and then translates each phrase.

![Yahoo's bipartite query-document graph](https://eugeneyan.com/assets/yahoo-click-graph.webp "Yahoo's bipartite query-document graph")

An example of Yahoo's bipartite query-document graph ([source](https://www.kdd.org/kdd2016/subtopic/view/ranking-relevance-in-yahoo-search))

Each query is typically translated into hundreds of candidates. Candidates are scored on three groups of features: query features (e.g., number of tokens in query, number of stop words, language model score), translated query features (same as query features), and similarity between the original query and translated query (e.g., [Jaccard similarity](https://en.wikipedia.org/wiki/Jaccard_index) between shared URLs, word-level cosine similarity, etc). The similarity features were found to be the most important.

Finally, the original query and top-scoring translated query are both used to retrieve documents. The final result set is a union of documents matching either query. For documents that match both queries, their max score is used.

## Graph-based: Adding concepts and relationships

Graph-based approaches involve building and using a **knowledge graph to expand queries and improve retrieval**. The most famous example of a knowledge graph is probably Google’s, [introduced](https://blog.google/products/search/introducing-knowledge-graph-things-not/) almost 10 years ago. It has nodes for people, places, things, etc, and edges to connect them together. This is how Google provides search result summaries, sometimes leading to interesting findings.

![Google's knowledge graph powers result summaries](https://eugeneyan.com/assets/google-kgraph.webp "Google's knowledge graph powers result summaries")

Google's knowledge graph powers result summaries ([source](https://blog.google/products/search/introducing-knowledge-graph-things-not/))

During query time, the query is parsed and tagged to the relevant concepts (i.e., nodes) in the knowledge graph. The query can then be expanded—to include relevant concepts—by finding the closest nodes in the knowledge graphs.

Building a knowledge graph is taxing. Nonetheless, we can bootstrap one by using [WordNet](https://en.wikipedia.org/wiki/WordNet), a lexical database of semantic relationships between words (available in more than 200 languages!) or [ConceptNet](https://en.wikipedia.org/wiki/Open_Mind_Common_Sense#ConceptNet), a semantic network where edges are assertions of commonsense between concepts (e.g., “is a”, “is used for”, “is made of”). Another approach is to mine [Wikipedia redirects](https://en.wikipedia.org/wiki/Wikipedia:Redirect).

![An example of ConceptNet with synonym, part of, and form of relationships](https://eugeneyan.com/assets/conceptnet.webp "An example of ConceptNet with synonym, part of, and form of relationships")

ConceptNet with synonym, part of, and form of relationships ([source](https://conceptnet.io/))

**[Uber shared about how they use a knowledge graph for search](https://eng.uber.com/uber-eats-query-understanding/).** First, they developed an ontology to describe the entities of the graph and the relationships between them. For example, foods and cuisines are related by `countryOfOrigin` while each entity can be a `subCategoryOf` another entity.

Then, they ingest and transform data from multiple sources to fit their ontology. Next, entities and edges are deduplicated, and new edges are built across multiple data sources. For example, the same restaurant on Foursquare and internal data should be represented as the same node. This connects disparate restaurant data from multiple sources via the same node—looking up a restaurant should return metadata from all data sources.

Then, they annotate restaurants and menu items with tags based on graph nodes—this is done offline. During query time (i.e., online), queries are annotated and expanded—by traversing the graph—in real-time to increase recall.

For example, if a user queries for “Asian”, the graph expands the search to include subsets such as “Chinese” and “Japanese”. Similarly, a query for “Udon” can be expanded to include related terms such as “Ramen”, “Soba”, and “Japanese”. The graph also includes location as an edge. Thus, if a restaurant is outside a user’s delivery zone, the graph can traverse to find similar cuisines in the user’s area.

![Uber's knowledge graph with country-of-origin and sub-category-of relationships](https://eugeneyan.com/assets/uber-graph.webp "Uber's knowledge graph with country-of-origin and sub-category-of relationships")

Uber's knowledge graph with `countryOfOrigin` and `subCategoryOf` relationships ([source](https://eng.uber.com/uber-eats-query-understanding/))

**[DoorDash also uses a knowledge graph](https://doordash.engineering/2020/12/15/understanding-search-intent-with-better-recall/)** and shared their ontology. They have three types of entities (i.e., nodes) in their knowledge graph (which is implemented in Neo4j):

* **Store**: Where the food is sold. It has the `_biz` suffix (e.g., `ihop_biz`).
* **Food category**: A coarse-grained descriptor of foods such as Chicken, Chinese, Fast Food. It has the `_cat` suffix (e.g., `breakfast_cat`).
* **Food tag**: A fine-grained descriptor of popular items sold, such as fried chicken, dim sum, tacos. It has the `_tag` suffix (e.g, `sandwich_tag`).

Entities are connected by three types of relationships:

* Each store will belong to a primary food category. For example, `ihop_biz` belongs to `breakfast_cat`.
* Each food category can have at most one parent food category. For example, `sandwich_cat` only has `breakfast_cat` as its parent, and `deli_cat` only has `sandwich_cat` as its parent. This enforces hierarchy between the food categories.
* Each food tag will belong to one food category. For example, `deli_tag`, `sandwich_tag`, and `cheesesteaks_tag` belong to `sandwich_cat`.

![DoorDash graph with relationships between stores, categories, and tags](https://eugeneyan.com/assets/doordash-graph.webp "DoorDash graph with relationships between stores, categories, and tags")

DoorDash graph with relationships between stores, categories, and tags ([source](https://doordash.engineering/2020/12/15/understanding-search-intent-with-better-recall/))

At query time, the knowledge graph expands on the underlying query concept. For example, when a customer searches for “KFC”, the KFC store nearest to the customer is returned as the top result. Then, the graph is used to expand the query to return restaurants with tags (e.g., `fried_chicken_tag`, `wings_tag`) that have the same primary category (i.e., `chicken_cat`).

![Query expansion for 'kfc'](https://eugeneyan.com/assets/doordash-kfc.webp "Query expansion for 'kfc'")

Query expansion for "kfc" ([source](https://doordash.engineering/2020/12/15/understanding-search-intent-with-better-recall/))

Similarly, when the customer enters a broad search query such as “Asian”, it is mapped to the `asian_cat`. This is then expanded to subcategories such as `thai_cat` and `chinese_cat`, and restaurants with tags belonging to these categories are retrieved. In the example below, Charm Thai contains the `thai_tag` which is part of the `thai_cat`, and HI Peninsula contains the `dim_sum_tag` which is part of the `chinese_cat`.

![Query expansion for 'asian'](https://eugeneyan.com/assets/doordash-asian.webp "Query expansion for 'asian'")

Query expansion for "asian" ([source](https://doordash.engineering/2020/12/15/understanding-search-intent-with-better-recall/))

> Know of other knowledge graphs used in search? [Please let me know!](https://twitter.com/eugeneyan)

## Pitfalls of lexical and graph-based approaches

Lexical-based approaches that treat each query as a bag-of-words can lead to incorrect results. DoorDash shared an example where customers searching for “California rolls” would get results for Mexican restaurants, instead of sushi places, because the tokens “California” and “roll” appear in the food menus of Mexican restaurants.

Lexical-based approaches also struggle to understand:

* **Hypernyms**: Broader categories of words, such as “hat” being a hypernym of “beret”, “cap”, and “snapback”.
* **Synonyms**: Different words, same meaning (e.g., “burgundy dress”, “red dress”).
* **Antonyms**: Words which have or imply opposite meaning. While “latex gloves” contain the same tokens as “latex free gloves”, they have the opposite meaning.

While this can be overcome with dictionaries and rules, it is tedious to manually curate and maintain these knowledge bases for each language.

Lexical-based approaches are also fragile to morphological variants (e.g., “woman” vs. “women”). While stemming can be applied, it is imperfect and can lead to information loss and errors. For example, “universal”, “university”, and “universe” all stem to “univers”. Similarly, this involves handcrafted rules which are a pain to create and maintain.

Finally, lexical-based approaches are sensitive to spelling errors. [One out of 10 queries is misspelled](https://blog.google/products/search/abcs-spelling-google-search/). While we can adopt spellcheckers and correctors, as DoorDash’s experience showed, spell correctors can be too aggressive and change the customer’s intent.

Though knowledge graphs help with increasing recall, they’re also a lot of manual work. From Uber and DoorDash’s experience, effort is needed to build the ontology, populate the knowledge graph with data from multiple sources, deduplicate nodes and edges, create new edges for better relationship mapping, and ensure the accuracy of nodes and edges.

Then, we need to tag catalog items with the nodes in the knowledge graphs offline, and tag and expand queries in real-time online. Knowledge graphs are costly to scale and maintain, and require constant manual curation and quality checks to ensure correctness.

To augment lexical and graph-based approaches, teams have increasingly turned to representation learning and embedding-based approaches.

## Embedding-based: Decomposing queries into numbers

Representation learning is a way to learn latent representations (i.e., embeddings) of items from data. They are latent because they cannot be observed directly. They’re also referred to as semantic embeddings because they learn the semantics of items well. It can be done **via self-supervised or supervised methods**.

The most commonly known self-supervised approach is probably [word2vec](https://en.wikipedia.org/wiki/Word2vec), which learns text embeddings given a corpus of text. It does this by training a network to predict a word’s neighbors (i.e., context) given a word via the skip-gram approach, or predict a word given its neighbors via the continuous-bag-of-words (CBOW) approach. A similar paradigm can be used to generate query embeddings.

Supervised methods usually use click or purchase events as labels. This involves training a model that takes a query and document as input and predicts the probability of click or purchase. The trained model is then used to generate query and document embeddings.

Once we have query and document embeddings, we can use them in query expansion and document retrieval. Embeddings have several advantages over the lexical-based approach. For example, they encode semantics and eliminate the need for a synonym dictionary; “handphone”, “cellphone”, and “mobile phone” are likely to be close in the embedding space. Furthermore, with character-level n-grams, query embeddings can be made less sensitive to morphological variants and spelling errors.

### Self-supervised techniques: No need for labels!

**[Yahoo’s approach to learning representations](https://www.kdd.org/kdd2016/subtopic/view/ranking-relevance-in-yahoo-search)** starts with creating a [bipartite graph](#yahoo-graph) of queries and clicked documents. Then, they extracted tokens from co-clicked queries to represent documents; tokens from more co-clicked queries are likely to be more representative of documents. Thus, the more queries two documents share, the closer they are, and vice versa. Similarly, queries that share many co-clicked documents are likely to have similar intent.

Each query is represented by a vector of tokens, with weights proportional to their frequencies in the query, and normalized to 1. Then, query and document vectors are propagated iteratively (somewhat like [alternating least squares](http://stanford.edu/~rezab/classes/cme323/S15/notes/lec14.pdf) for collaborative filtering), resulting in query and document embeddings in the same vector space. To get similarities between queries and documents, they compute the inner product of these vectors.

**[Uber used the GloVe algorithm](https://eng.uber.com/uber-eats-query-understanding/)** to learn query embeddings. GloVe (Global Vectors) creates word embeddings by learning word co-occurrence in a corpus. To apply the language modeling paradigm to search, each query is considered a word in a sentence, and queries are “next to each other” in the sentence (i.e., same context) if both queries lead to an order from the same restaurant. To put it another way, the restaurant is the context and two queries share the same context if they both lead to orders in the same restaurant.

![Queries leading to orders from the same restaurant have the same context](https://eugeneyan.com/assets/uber-embedding.webp "Queries leading to orders from the same restaurant have the same context")

Queries leading to orders from the same restaurant have the same context ([source](https://eng.uber.com/uber-eats-query-understanding/))

They start with constructing a Pointwise Mutual Information matrix with the search queries, where *a* and *b* are tuning params and *p(q1, q2)* is the joint distribution of *q1* and *q2*.

\[\operatorname{pmi}\left(q\_{1}, q\_{2}\right)=\log \frac{p\left(q\_{1}, q\_{2}\right)}{p\left(q\_{1}\right)^{a} p\left(q\_{2}\right)^{b}}\]

Then, they apply a GloVe-based factorization model to learn query embeddings. These query embeddings can then be used for query expansion (via approximate nearest neighbors) to improve search recall. For example, if a user searches for “tan tan noodle” (or more correctly, “dan dan noodle”) and there are no restaurants selling it nearby, it can be expanded to “Little Szechuan”, “Chinese”, and “Spicy Food”.

![Query expansion for 'tan tan noodle'](https://eugeneyan.com/assets/uber-expansion.webp "Query expansion for 'tan tan noodle'")

Query expansion for "tan tan noodle" ([source](https://eng.uber.com/uber-eats-query-understanding/))

**[GrubHub adopts a similar paradigm](https://bytes.grubhub.com/search-query-embeddings-using-query2vec-f5931df27d79)** using the skip-gram architecture and shared examples where the nearest neighbors for “Udon” and “Mediterranean” almost map 1:1 with a reference food graph. This provides assurance that the self-supervised approach can capture knowledge graph-like semantics via embeddings.

![Embeddings for 'udon' and 'mediterranean' and how they compare to the knowlege graph](https://eugeneyan.com/assets/grubhub-embedding.webp "Embeddings for 'udon' and 'mediterranean' and how they compare to the knowlege graph")

Embeddings for "udon" and "mediterranean" and how they compare to the knowlege graph ([source](https://bytes.grubhub.com/search-query-embeddings-using-query2vec-f5931df27d79))

### Supervised techniques: Improves modeling of our desired event

**[Amazon built semantic product search](https://arxiv.org/abs/1907.00937)** using customer behavioral data. Their neural net architecture shares embeddings across the query and product. Queries are fed into the model as they are while products are represented as an ordered bag-of-attributes (e.g., title, brand, color). They also tried learning attribute embeddings but it led to 5% lower recall (relative to concatenating attributes), likely due to the variability in accuracy and availability of structured data.

![Amazon's neural network architecture for semantic product search](https://eugeneyan.com/assets/amazon-search-nn.webp "Amazon's neural network architecture for semantic product search")

Amazon's neural network architecture for semantic product search ([source](https://arxiv.org/abs/1907.00937))

Average pooling is then applied to get a fixed-length embedding for the query and product. Relative to recurrent approaches such as LSTM and GRU, using average pooling made little difference (<0.5%) in mean average precision and recall@100 while requiring less computation, training time, and inference latency.

They initially adopted a two-part hinge loss. First, *ŷ* is the cosine similarity between query and product embeddings, and *y* = 1 if the product is purchased (in response to the query) and zero otherwise. The hinge loss ensures that *ŷ* > 0.9 when *y* = 1 and *ŷ* < 0.2 when *y* = 0. However, they found a large overlap in score distributions between random negatives (red) and purchased positives (green) due to products that were impressed but not purchased.

Thus, they updated the two-part loss to also consider products that were impressed but not purchased, where *ŷ* < 0.55 where *y* = impressed but not purchased. This improved the separation of scores between random negatives (red), impressed but not purchased negatives (grey), and purchased positives (green).

![Score distribution with two-part (left) and three-part (right) hinge loss](https://eugeneyan.com/assets/amazon-search-hinge-loss.webp "Score distribution with two-part (left) and three-part (right) hinge loss")

Score distribution with two-part (left) and three-part (right) hinge loss ([source](https://arxiv.org/abs/1907.00937))

To tokenize queries and products, they applied tokenization approaches such as:

* Work unigrams and n-grams: N-grams capture phrase-level information that unigrams don’t. For example, “chocolate milk” and “milk chocolate” are different though they share the same unigrams.
* Character tri-grams: These are robust to types and handle compound words (e.g., “amazontv”, “firetvstick”) well. They also capture similarity of model parts.

![Example tokens for the query 'artistic iphone 6s case'](https://eugeneyan.com/assets/amazon-search-tokens.webp "Example tokens for the query 'artistic iphone 6s case'")

Example tokens for the query "artistic iphone 6s case" ([source](https://arxiv.org/abs/1907.00937))

It is unfeasible to have a vocabulary of all possible word n-grams as dictionary size grows exponentially with *n*. Thus, they maintain a vocabulary of hundreds of thousands of n-grams based on token frequency. To handle unseen words, they hash out-of-vocabulary (OOV) tokens to additional embedding bins. By using fixed hash functions and shared query-document embeddings, unseen tokens in both the query and products map to the same embedding vector. A bin size 5-10x larger than vocab size is used. Then, all tokens are combined as a single bag-of-tokens (i.e., unordered, equal weight).

**[Facebook’s embedding-based search](https://arxiv.org/abs/2006.11632)** adopts a two-tower approach with separate towers for queries and documents. The model is formulated as a ranking problem based on distance between a query and document. Cosine similarity is used as the distance metric.

![Facebook's two-tower architecture that includes location and social features](https://eugeneyan.com/assets/fb-search-nn.webp "Facebook's two-tower architecture that includes location and social features")

Facebook's two-tower architecture that includes location and social features ([source](https://arxiv.org/abs/2006.11632))

They use triplet loss to approximate the recall objective. For a given triplet *(q, d+, d-)*, *q* is the query while *d+* and *d-* are the associated positive and negative documents. *D(q, d)* is the distance between the query and document embedding and *m* is the margin enforced between positive and negative pairs. The intuition is to separate the positive and negative pairs by the distance margin.

\[L=\sum\_{i=1}^{N} \max \left(0, D\left(q^{(i)}, d\_{+}^{(i)}\right)-D\left(q^{(i)}, d\_{-}^{(i)}\right)+m\right)\]

For positive labels, they tried using clicks and impressions. Why impressions as positive labels? The intuition is to teach the model to return the same set of results that will be ranked high by the ranker. Both were found to be equally effective, though adding impressions to click data did not improve the model.

For negative labels, they tried using random samples and impressed-but-not-clicked samples. The model trained on the latter (i.e., non-clicked impressions) had worse recall relative to random negatives, with a 55% recall drop for the people embedding model. (Contrast this to Amazon’s approach where accounting for non-click impressions led to improved results.) They hypothesized that non-click impressions bias towards hard cases where the documents match the query on at least one factor. In contrast, the majority of documents are easy cases that don’t match the query at all. Thus, using non-click impressions bias the training data, making it not representative of the actual retrieval task.

For text features, they used character and word n-grams. Adding word n-grams led to small but consistent improvements (+1.5% recall). Similar to Amazon, they found the cardinality of word n-grams too high (352 million for query trigrams) and had to apply hashing to reduce the size of the embedding table.

As additional context, they included location features of the query (e.g., city, country, language) and document (e.g., group location). They also included social embedding features that were trained via a separate embedding model to embed users and entities in the social graph.

As a final example, we look at **[JD’s semantic retrieval model](https://arxiv.org/abs/2006.02282)** which takes it one step further with the introduction of multiple query heads.

![JD's two-tower architecture with multiple query heads](https://eugeneyan.com/assets/jd-search-nn.webp "JD's two-tower architecture with multiple query heads")

JD's two-tower architecture with multiple query heads ([source](https://arxiv.org/abs/2006.02282))

The item tower is straightforward where embeddings from multiple attributes (e.g., title, brand, seller) are concatenated into a single vector (this is similar to Amazon’s approach though they have embeddings for each attribute). Then, the vector goes through multiple [Rectified Linear Unit](https://en.wikipedia.org/wiki/Rectifier_(neural_networks)) layers. The output item embedding is finally normalized to be the same length as the query embedding.

The query tower is novel in that it has multiple heads (à la [Transformer](https://en.wikipedia.org/wiki/Transformer_(machine_learning_model))). An additional projection layer passes the dense input layer into *k* dense representations. These *k* representations are then passed into *k* separate encoders, each with their own parameters. As a result, each query head captures different semantic meanings for a query, such as different popular brands for a product query (e.g., Apple and Samsung for “cellphone”) and different products for a brand query (e.g., phones and monitors for “Samsung”).

To get query-item similarity, they compute a weighted sum of all inner products between the multiple query embeddings and the single item embedding. The weights are computed from the softmax of the same set of inner products, with a temperature parameter (β). The higher the temperature, the more uniform the weights will be. As temperature goes to zero, the similarity score becomes equivalent to selecting the largest inner product.

\[w\_{i}=\frac{\exp \left(e\_{i}^{\top} g / \beta\right)}{\sum\_{j=1}^{m} \exp \left(e\_{j}^{\top} g / \beta\right)}\]

To create negative item labels, they used a mix of random negatives and batch negatives. Random negatives are uniformly sampled from all items. Thus, each item has the same probability of showing up as a negative. However, this is computationally expensive as each random negative has to go through the item tower (to get the item embedding). Batch negatives come from the other query-item pairs in the same batch. For a query-item pair, the other positive items in the same batch are used as item negatives. They found that a proportion of 0.5 - 0.75 random negatives works well.

![Using 0.5 - 0.75 random negatives leads to optimal results](https://eugeneyan.com/assets/jd-negative-mix.webp "Using 0.5 - 0.75 random negatives leads to optimal results")

Using 50 - 75% random negatives leads to optimal results ([source](https://arxiv.org/abs/2006.02282))

## Embedding-based approaches have pitfalls too

For example, Uber shared that “halal” may expand to “middle eastern”, “mediterranean”, or South-East Asian cuisines and retrieve restaurants that may not be halal, leading to a poor customer experience. Furthermore, representation learning requires a large amount of behavioral data that might not be available when the search system is launched in a new marketplace with little to no data.

Thus, I’ve found **lexical, graph, and embedding-based approaches to be complementary**. Most search systems use embedding-based approaches to augment lexical and/or graph-based approaches (instead of replacing them completely). For example:

* Uber uses its knowledge graph with query embeddings for query expansion
* Amazon’s semantic matching augments keyword and behavioral matching
* Facebook’s semantic matching augments their existing boolean-matching

![Amazon's (left, semantic matching) and Facebook's (right, NN Operator in the retrieval box) embedding-based approach augmenting existing methods](https://eugeneyan.com/assets/embedding-augmentation.webp "Amazon's (left, semantic matching) and Facebook's (right, NN Operator in the retrieval box) embedding-based approach augmenting existing methods")

Amazon's (left, semantic matching) and Facebook's (right, NN Operator in the retrieval box) embedding-based approach augmenting existing methods ([source](https://arxiv.org/abs/1907.00937), [source](https://arxiv.org/abs/2006.11632))

## Conclusion: Start lexical, then embeddings

There’s no one way to handle search queries. Lexical-based techniques are a fundamental, content-based approach that doesn’t require building a knowledge graph or large amounts of behavioral data—if you’re building a search system from scratch, perhaps start here. ElasticSearch and Lucene largely work out of the box.

If you find yourself reaching the point of diminishing returns with lexical or graph-based approaches, especially with long-tail queries, try augmenting it with query embeddings learned via self-supervised representation learning—they’re bang for buck.

Am I missing anything? Reach out and let me know!

## References

**Thanks** to Yang Xinyi and [David Golden](https://xdg.me/) for reading drafts of this. Thanks to [Alex Egg](https://twitter.com/eggie5) for initial discussion on this topic.

If you found this useful, please cite this write-up as:

> Yan, Ziyou. (Apr 2021). Search: Query Matching via Lexical, Graph, and Embedding Methods. eugeneyan.com.
> https://eugeneyan.com/writing/search-query-matching/.

or

```
@article{yan2021query,
  title   = {Search: Query Matching via Lexical, Graph, and Embedding Methods},
  author  = {Yan, Ziyou},
  journal = {eugeneyan.com},
  year    = {2021},
  month   = {Apr},
  url     = {https://eugeneyan.com/writing/search-query-matching/}
}
```

Share on:

### Test yourself

1. Where would each of the three approaches (lexical, graph, embedding) fail on the kind of queries your CodePipeline agent users would ask?
2. Yan's recommendation is "start lexical, then embeddings." What's the failure mode of the reverse order — going embeddings-first?
3. After reading, in one sentence: what is a sparse representation actually representing, and what is a dense one?

---

## RAG is More Than Just Embedding Search

*Jason Liu · jxnl.co · 17 September 2023 · [https://jxnl.co/writing/2023/09/17/rag-is-more-than-embeddings/](https://jxnl.co/writing/2023/09/17/rag-is-more-than-embeddings/)*

> Short and sharp. The "dumb RAG" Jason describes is what most people mean when they say "we built a RAG." Note the four failure modes — query-document mismatch, monolithic backend, single-string queries, no planning. Then watch the reframe: query understanding turns retrieval from *what string do I search* into *what dispatches where, with what filters, over what time range*. The Metaphor and personal-assistant examples are concrete; the general lesson is that production RAG is a structured-output problem in front of multiple backends.

# RAG is more than just embedding search

With the advent of large language models (LLM), retrieval augmented generation (RAG) has become a hot topic. However throught the past year of [helping startups](https://jxnl.co) integrate LLMs into their stack I've noticed that the pattern of taking user queries, embedding them, and directly searching a vector store is effectively demoware.

What is RAG?

Retrieval augmented generation (RAG) is a technique that uses an LLM to generate responses, but uses a search backend to augment the generation. In the past year using text embeddings with a vector databases has been the most popular approach I've seen being socialized.

![RAG](https://jxnl.co/writing/img/dumb_rag.png)

Simple RAG that embedded the user query and makes a search.

 

So let's kick things off by examining what I like to call the 'Dumb' RAG Model—a basic setup that's more common than you'd think.

If you want to learn more about I systematically improve RAG applications check out my free 6 email improving rag crash course

[Check out the free email course here](https://dub.link/6wk-rag-email)

## The 'Dumb' RAG Model

When you ask a question like, "what is the capital of France?" The RAG 'dumb' model embeds the query and searches in some unopinonated search endpoint. Limited to a single method API like `search(query: str) -> List[str]`. This is fine for simple queries, since you'd expect words like 'paris is the capital of france' to be in the top results of say, your wikipedia embeddings.

### Why is this a problem?

* **Query-Document Mismatch**: This model assumes that query embedding and the content embedding are similar in the embedding space, which is not always true based on the text you're trying to search over. Only using queries that are semantically similar to the content is a huge limitation!
* **Monolithic Search Backend**: Assumes a single search backend, which is not always the case. You may have multiple search backends, each with their own API, and you want to route the query to vector stores, search clients, sql databases, and more.
* **Limitation of text search**: Restricts complex queries to a single string (`{query: str}`), sacrificing expressiveness, in using keywords, filters, and other advanced features. For example, asking `what problems did we fix last week` cannot be answered by a simple text search since documents that contain `problem, last week` won't be present every week or may reference the wrong period of time entirely.
* **Limited ability to plan**: Assumes that the query is the only input to the search backend, but you may want to use other information to improve the search, like the user's location, or the time of day using the context to rewrite the query. For example, if you present the language model of more context its able to plan a suite of queries to execute to return the best results.

Now let's dive into how we can make it smarter with query understanding. This is where things get interesting.

## Improving the RAG Model with Query Understanding

Much of this work has been inspired by / done in collab with a few of my clients at [new.computer](https://new.computer), [Metaphor Systems](https://metaphor.systems), and [Naro](https://narohq.com), go check them out!

Ultimately what you want to deploy is a [system that understands](https://en.wikipedia.org/wiki/Query_understanding) how to take the query and rewrite it to improve precision and recall.

![RAG](https://jxnl.co/writing/img/query_understanding.png)

Query Understanding system routes to multiple search backends.

 

Not convinced? Let's move from theory to practice with a real-world example. First up, Metaphor Systems.

## Whats instructor?

Instructor uses Pydantic to simplify the interaction between the programmer and language models via the function calling API.

* **Widespread Adoption**: Pydantic is a popular tool among Python developers.
* **Simplicity**: Pydantic allows model definition in Python.
* **Framework Compatibility**: Many Python frameworks already use Pydantic.

Take [Metaphor Systems](https://metaphor.systems), which turns natural language queries into their custom search-optimized query. If you take a look web UI you'll notice that they have an auto-prompt option, which uses function calls to furthur optimize your query using a language model, and turns it into a fully specified metaphor systems query.

![Metaphor Systems](https://jxnl.co/writing/img/meta.png)

Metaphor Systems UI

 

If we peek under the hood, we can see that the query is actually a complex object, with a date range, and a list of domains to search in. It's actually more complex than this but this is a good start. We can model this structured output in Pydantic using the instructor library

```
class DateRange(BaseModel):
    start: datetime.date
    end: datetime.date

class MetaphorQuery(BaseModel):
    rewritten_query: str
    published_daterange: DateRange
    domains_allow_list: List[str]

    async def execute():
        return await metaphor.search(...)
```

Note how we model a rewritten query, range of published dates, and a list of domains to search in. This powerful pattern allows the user query to be restructured for better performance without the user having to know the details of how the search backend works.

```
import instructor
from openai import OpenAI

# Enables response_model in the openai client
client = instructor.patch(OpenAI())

query = client.chat.completions.create(
    model="gpt-4",
    response_model=MetaphorQuery,
    messages=[
        {
            "role": "system",
            "content": "You're a query understanding system for the Metafor Systems search engine. Here are some tips: ..."
        },
        {
            "role": "user",
            "content": "What are some recent developments in AI?"
        }
    ],
)
```

**Example Output**

```
{
  "rewritten_query": "novel developments advancements ai artificial intelligence machine learning",
  "published_daterange": {
    "start": "2021-06-17",
    "end": "2023-09-17"
  },
  "domains_allow_list": ["arxiv.org"]
}
```

This isn't just about adding some date ranges. It's about nuanced, tailored searches, that are deeply integrated with the backend. Metaphor Systems has a whole suite of other filters and options that you can use to build a powerful search query. They can even use some chain of thought prompting to improve how they use some of these advanced features.

```
class DateRange(BaseModel):
    start: datetime.date
    end: datetime.date
    chain_of_thought: str = Field(
        None,
        description="Think step by step to plan what is the best time range to search in"
    )
```

Now, let's see how this approach can help model an agent like personal assistant.

## Case Study 2: Personal Assistant

Another great example of this multiple dispatch pattern is a personal assistant. You might ask, "What do I have today?", from a vague query you might want events, emails, reminders etc. That data will likely exist in multiple backends, but what you want is one unified summary of results. Here you can't assume that text of those documents are all embedded in a search backend. There might be a calendar client, email client, across personal and profession accounts.

```
class ClientSource(enum.Enum):
    GMAIL = "gmail"
    CALENDAR = "calendar"

class SearchClient(BaseModel):
    query: str
    keywords: List[str]
    email: str
    source: ClientSource
    start_date: datetime.date
    end_date: datetime.date

    async def execute(self) -> str:
        if self.source == ClientSource.GMAIL:
            ...
        elif self.source == ClientSource.CALENDAR:
            ...

class Retrieval(BaseModel):
    queries: List[SearchClient]

    async def execute(self) -> str:
        return await asyncio.gather(*[query.execute() for query in self.queries])
```

Now we can call this with a simple query like "What do I have today?" and it will try to async dispatch to the correct backend. It's still important to prompt the language model well, but we'll leave that for another day.

```
import instructor
from openai import OpenAI

# Enables response_model in the openai client
client = instructor.patch(OpenAI())

retrieval = client.chat.completions.create(
    model="gpt-4",
    response_model=Retrieval,
    messages=[
        {"role": "system", "content": "You are Jason's personal assistant."},
        {"role": "user", "content": "What do I have today?"}
    ],
)
```

**Example Output**

```
{
    "queries": [
        {
            "query": None,
            "keywords": None,
            "email": "[email protected]",
            "source": "gmail",
            "start_date": "2023-09-17",
            "end_date": None
        },
        {
            "query": None,
            "keywords": ["meeting", "call", "zoom"]]],
            "email": "[email protected]",
            "source": "calendar",
            "start_date": "2023-09-17",
            "end_date": None

        }
    ]
}
```

Notice that we have a list of queries that route to different search backends (email and calendar). We can even dispatch them async to be as performant as possible. Not only do we dispatch to different backends (that we have no control over), but you are likely going to render them to the user differently as well. Perhaps you want to summarize the emails in text, but you want to render the calendar events as a list that they can scroll across on a mobile app.

Both of these examples showcase how both search providers and consumers can use `instructor` to model their systems. This is a powerful pattern that allows you to build a system that can be used by anyone, and can be used to build an LLM layer, from scratch, in front of any arbitrary backend.

## Further Reading

To deepen your understanding of RAG systems and their implementation, explore these related articles:

These resources offer valuable perspectives on building, optimizing, and maintaining effective RAG systems in various contexts.

If you want to learn more about I systematically improve RAG applications check out my free 6 email improving rag crash course

[Check out the free email course here](https://dub.link/6wk-rag-email)

### Test yourself

1. Pick a retrieval failure you've actually seen — yours or a coworker's. Which of Jason's four failure modes was it?
2. What in your current stack would you need to add to do query understanding the way Metaphor Systems does?
3. Where does "search" stop and "agent" start once query understanding is in the picture?

---

## Obsidian-Copilot: An Assistant for Writing & Reflecting

*Eugene Yan · eugeneyan.com · 2023 · [https://eugeneyan.com/writing/obsidian-copilot/](https://eugeneyan.com/writing/obsidian-copilot/)*

> A concrete hybrid-retrieval reference. Eugene runs BM25 (via OpenSearch) *alongside* a dense semantic search (`e5-small-v2`) and merges the results. Read this to nail down what each layer is actually catching: keyword search for names/IDs/acronyms; semantic search for conceptual neighbors. Pay close attention to where and how the results are combined — that boundary is where most production hybrid systems live or die.

What would a copilot for writing and thinking look like? To try answering this question, I built a prototype: Obsidian-Copilot. Given a section header, it helps draft a few paragraphs via [retrieval-augmented generation](https://docs.aws.amazon.com/sagemaker/latest/dg/jumpstart-foundation-models-customize-rag.html). Also, if you write a daily journal, it can help you reflect on the past week and plan for the week ahead.

![Obsidian Copilot: Helping to write drafts and reflect on the week](https://eugeneyan.com/assets/copilot.webp "Obsidian Copilot: Helping to write drafts and reflect on the week")

Obsidian Copilot: Helping to write drafts and reflect on the week

Here’s a short 2-minute demo. The code is available at [obsidian-copilot](https://github.com/eugeneyan/obsidian-copilot).

VIDEO

## How does it work?

**We start by parsing documents into chunks.** A sensible default is to [chunk documents by token length](https://github.com/hwchase17/langchain/blob/master/langchain/text_splitter.py#L58), typically 1,500 to 3,000 tokens per chunk. However, I found that this [didn’t work very well](/writing/llm-experiments/#documents-may-be-inadequately-chunked). A better approach might be to chunk by paragraphs (e.g., split on `\n\n`).

Given that my notes are mostly in bullet form, I [chunk by top-level bullets](https://github.com/eugeneyan/obsidian-copilot/blob/main/src/prep/build_vault_dict.py#L73): Each chunk is made up of a single top-level bullet and its sub-bullets. There are usually 5 to 10 sub-bullets per top-level bullet making each chunk similar in length to a paragraph.

```
chunks = defaultdict()
current_chunk = []
chunk_idx = 0
current_header = None

for line in lines:

    if '##' in line:  # Chunk header = Section header
        current_header = line
    
    if line.startswith('- '):  # Top-level bullet
        if current_chunk:  # If chunks accumulated, add it to chunks
            if len(current_chunk) >= min_chunk_lines:
                chunks[chunk_idx] = current_chunk
                chunk_idx += 1
            current_chunk = []  # Reset current chunk
            if current_header:
                current_chunk.append(current_header)
    
    current_chunk.append(line)
```

Next, we build an OpenSearch index and a semantic index on these chunks. In a previous experiment, I found that [embedding-based retrieval alone might be insufficient](/writing/llm-experiments/#embedding-based-retrieval-alone-might-be-insufficient) and thus added classical search (i.e., [BM25](https://en.wikipedia.org/wiki/Okapi_BM25) via OpenSearch) in this prototype.

**For OpenSearch, we start by configuring filters and fields.** We include [filters](https://www.elastic.co/guide/en/elasticsearch/reference/7.17/analysis-tokenfilters.html) such as [stripping HTML](https://www.elastic.co/guide/en/elasticsearch/reference/7.17/analysis-htmlstrip-charfilter.html), [removing possessives](https://lucene.apache.org/core/9_6_0/analysis/common/org/apache/lucene/analysis/en/EnglishPossessiveFilter.html) (i.e., the trailing ‘s in words), removing stopwords, and basic stemming. These filters are applied on both documents (during indexing) and queries. We also specify the fields we want to index and their respective types. Types matter because filters are applied on text fields (e.g., title, chunk) but not on keyword fields (e.g., path, document type). We don’t apply preprocessing on file paths to keep them as they are.

```
'mappings': {
	'properties': {
		'title': {'type': 'text', 'analyzer': 'english_custom'},
		'type': {'type': 'keyword'},
		'path': {'type': 'keyword'},
		'chunk_header': {'type': 'text', 'analyzer': 'english_custom'},
		'chunk': {'type': 'text', 'analyzer': 'english_custom'},
	}
}
```

When querying, we apply [boosts](https://www.elastic.co/guide/en/elasticsearch/reference/7.17/mapping-boost.html) to make some fields count more towards the relevance score. In this prototype, I arbitrarily [boosted](https://github.com/eugeneyan/obsidian-copilot/blob/main/src/prep/build_opensearch_index.py#L163) titles by 5x and chunk headers (i.e., top-level bullets) by 2x. Retrieval can be improved by tweaking these boosts as well as [other features](https://www.elastic.co/guide/en/elasticsearch/reference/7.17/query-dsl-rank-feature-query.html).

**For semantic search, we start by picking an embedding model.** I referred to the [Massive Text Embedding Benchmark Leaderboard](https://huggingface.co/spaces/mteb/leaderboard), sorted it on descending order of retrieval score, and picked a model that had a good balance of embedding dimension and score.

This led me to [e5-small-v2](https://huggingface.co/intfloat/e5-small-v2). Currently, it’s ranked a respectable 7th, right below text-embedding-ada-002. What’s impressive is its embedding size of 384 which is far smaller than what most models have (768 - 1,536). And while it supports a maximum sequence length of only 512, this is sufficient given my shorter chunks. (More details in the paper [Text Embeddings by Weakly-Supervised Contrastive Pre-training](https://arxiv.org/abs/2212.03533).) After embedding these documents, we store them in a `numpy` array.

During query time, we tokenize and embed the query, do a dot product with the document embedding array, and take the top *n* results (in this case, 10).

```
def query_semantic(query, tokenizer, model, doc_embeddings_array, n_results=10):
    query_tokenized = tokenizer(f'query: {query}', max_length=512, padding=False, truncation=True, return_tensors='pt')
    outputs = model(**query_tokenized)
    query_embedding = average_pool(outputs.last_hidden_state, query_tokenized['attention_mask'])
    query_embedding = F.normalize(query_embedding, p=2, dim=1).detach().numpy()

    cos_sims = np.dot(doc_embeddings_array, query_embedding.T)
    cos_sims = cos_sims.flatten()

    top_indices = np.argsort(cos_sims)[-n_results:][::-1]

    return top_indices
```

If you’re thinking of using the e5 models, remember to add the necessary prefixes during preprocessing. For documents, you’ll have to prefix them with “`passage:‎` ” and for queries, you’ll have to prefix them with “`query:‎` ”

**The retrieval service is a FastAPI app.** Given an input query, it [performs both BM25 and semantic search](https://github.com/eugeneyan/obsidian-copilot/blob/main/src/app.py#L144), deduplicates the results, and returns the documents’ text and associated title. The latter is used to [link source documents](https://www.youtube.com/watch?v=QRJW5jT5VRA&t=72s) when generating the draft.

To start the OpenSearch node and semantic search + FastAPI server, we use a [simple-docker compose file](https://github.com/eugeneyan/obsidian-copilot/blob/main/docker-compose.yml). They each run in their own containers, bridged by a common network. For convenience, we also define common commands in a [Makefile](https://github.com/eugeneyan/obsidian-copilot/blob/main/Makefile).

**Finally, we integrate with Obsidian via a TypeScript plugin.** The [obsidian-plugin-sample](https://github.com/obsidianmd/obsidian-sample-plugin) made it easy to get started and I added functions to display retrieved documents in a new tab, query APIs, and stream the output. (I’m new to TypeScript so feedback appreciated!)

## What else can we apply this to?

While this prototype uses local notes and journal entries, it’s not a stretch to imagine the copilot retrieving from other documents (online). For example, team documents such as product requirements and technical design docs, internal wikis, and even code. I’d guess that’s what Microsoft, Atlassian, and Notion are working on right now.

It also extends beyond personal productivity. Within my field of recommendations and search, researchers and practitioners are excited about [layering LLM-based generation](https://arxiv.org/abs/2306.02887) on top of existing systems and products to improve the customer experience. (I expect we’ll see some of this in production by the end of the year.)

## Ideas for improvement

One idea is to try LLMs with larger context sizes that allow us to feed in entire documents instead of chunks. (This may help with retrieval recall but puts more onus on the LLM to identify the relevant context for generation.) Currently, I’m using gpt-3.5-turbo which is a good balance of speed and cost. Nonetheless, I’m excited to try claude-1.3-100k and provide entire documents as context.

Another idea is to augment retrieval with web or internal search when necessary. For example, when documents and notes go stale (e.g., based on last updated timestamp), we can look up the web or internal documents for more recent information.

• • •

Here’s the [GitHub repo](https://github.com/eugeneyan/obsidian-copilot) if you’re keen to try. Start by cloning the repo and updating the path to your obsidian-vault and huggingface hub cache. The latter saves us from downloading the tokenizer and model each time you start the containers.

```
git clone https://github.com/eugeneyan/obsidian-copilot.git

# Open Makefile and update the following paths
export OBSIDIAN_PATH = /Users/eugene/obsidian-vault/
export TRANSFORMER_CACHE = /Users/eugene/.cache/huggingface/hub
```

Then, build the image and indices before starting the retrieval app.

```
# Build the docker image
make build

# Start the opensearch container and wait for it to start. 
# You should see something like this: [c6587bf83572] Node 'c6587bf83572' initialized
make opensearch

# In ANOTHER terminal, build your artifacts (this can take a while)
make build-artifacts

# Start the app. You should see this: Uvicorn running on http://0.0.0.0:8000
make run
```

Finally, install the copilot plugin, enable it in community plugin settings, and update the API key. You’ll have to restart your Obsidian app if you had it open before installation.

If you tried it, I would love to hear how it went, especially where it didn’t work well and how it can be improved. Or if you’ve been working with retrieval-augmented generation, I’d love to hear about your experience so far!

If you found this useful, please cite this write-up as:

> Yan, Ziyou. (Jun 2023). Obsidian-Copilot: An Assistant for Writing & Reflecting. eugeneyan.com.
> https://eugeneyan.com/writing/obsidian-copilot/.

or

```
@article{yan2023copilot,
  title   = {Obsidian-Copilot: An Assistant for Writing & Reflecting},
  author  = {Yan, Ziyou},
  journal = {eugeneyan.com},
  year    = {2023},
  month   = {Jun},
  url     = {https://eugeneyan.com/writing/obsidian-copilot/}
}
```

Share on:

### Test yourself

1. What does BM25 catch in Eugene's setup that e5-small-v2 misses? What does e5 catch that BM25 misses?
2. The merge step combines results from both retrieval paths. What's the simplest correct way to do that, and where would it go wrong at scale?
3. If you had to cut one of the two retrieval paths from your own work, which would you cut and what would degrade?

---

## Why Grep Beat Embeddings in Our SWE-Bench Agent (Lessons from Augment)

*Jason Liu · jxnl.co · 11 September 2025 · [https://jxnl.co/writing/2025/09/11/why-grep-beat-embeddings-in-our-swe-bench-agent-lessons-from-augment/](https://jxnl.co/writing/2025/09/11/why-grep-beat-embeddings-in-our-swe-bench-agent-lessons-from-augment/)*

> Counterprogramming, and directly relevant to your day job. Embeddings are the *default* answer for retrieval right now. Here, on a code-search benchmark, literal grep beat them. The reason is the structure of the corpus and the queries — code is symbolic, exact, and small relative to the embedding-model context. As you read, build the rule for yourself: *when does a sparse / exact-match retrieval beat a dense / semantic one?* This is the rule you need to make sharper architectural choices on agent work in code.

# Why Grep Beat Embeddings in Our SWE-Bench Agent (Lessons from Augment)

I hosted Colin Flaherty, previously a founding engineer at Augment and co-author of Meta's Cicero AI, to discuss autonomous coding agents and retrieval systems. This session explores how agentic approaches are transforming traditional RAG systems, what we can learn from state-of-the-art coding agents, and how these insights might apply to other domains.

[▶️ See How Grep Beat Complex Embeddings](https://maven.com/p/5f4d74)

## Do agents make traditional RAG obsolete?

Colin shared his experience building an agent for SWE-Bench Verified, a canonical AI coding evaluation where agents implement code changes based on problem descriptions. His team's agent reached the top of the leaderboard with a surprising discovery: embedding-based retrieval wasn't the bottleneck they expected.

"We explored adding various embedding-based retrieval tools, but found that for SweeBench tasks this was not the bottleneck - grep and find were sufficient," Colin explained. This initially surprised him, as he expected embedding models to be significantly more powerful.

The evolution of code retrieval complexity has followed a clear progression:

* 2023 (Completions): Simple retrieval with low latency requirements
* 2024 (Chatbots): More complex retrieval across multiple files
* 2025 (Agents): Highly complex retrieval across many parts of codebases

When examining how the agent solved problems, Colin observed it would use simple tools like grep and find persistently, trying different approaches until it found what it needed. The agent's persistence effectively compensated for less sophisticated tools.

***Key Takeaway:*** Agents don't necessarily make traditional RAG obsolete, but they change how we should think about retrieval systems. The persistence and course-correction capabilities of agents can sometimes overcome limitations in the underlying retrieval tools.

**Benefits of agentic retrieval with simple tools** Agentic retrieval with grep and find offers several advantages:

1. Iterative retrieval becomes much simpler - instead of complex multi-step embedding processes, agents can simply run multiple searches and refine as they go
2. Token budget management is straightforward - when the agent hits token limits, it can simply truncate old tool calls and rerun them if needed
3. Implementation is low-effort - no need to maintain vector databases, syncing mechanisms, or other infrastructure
4. Course correction happens naturally - if one search approach fails, the agent tries another

However, these simple approaches have clear limitations:

* They don't scale well to large codebases
* They struggle with unstructured natural language content
* They're relatively slow and expensive compared to optimized embedding lookups

The best approach might be combining both worlds - an agentic loop with access to high-quality embedding models as tools.

**How to architect retrieval systems for different needs** When deciding between traditional RAG, agent+grep/find, or agent+embeddings, Colin recommends considering several factors:

* Quality: How good is the final output?
* Latency: How quickly does the system respond?
* Cost: What are the computational expenses?
* Reliability: Does the system correct itself when it fails?
* Scalability: How well does it handle large indices?
* Maintenance effort: How much engineering work is required?

Traditional RAG offers decent quality with excellent speed, low cost, and high scalability, but lacks course correction. Agent+grep provides excellent quality and reliability but struggles with speed, cost, and scale. Agent+embeddings combines the best of both but remains slow and expensive.

***Key Takeaway:*** Don't throw away your existing retrieval systems - instead, expose them as tools to agents. This gives you the benefits of both approaches while allowing you to optimize based on your specific constraints. For implementation guidance, see the [Context Engineering approach to tool response design](../../../08/27/facets-context-engineering/), which shows how to structure tool outputs to give agents better peripheral vision of the information landscape.

**Evaluating agentic retrieval systems** Colin emphasized a "vibe-first" approach to evaluation:

"Start with 5-10 examples and do end-to-end vibe checks before moving to quantitative evaluation. With natural language systems, you can learn so much just from looking at a few examples."

He noted that improving embedding models doesn't necessarily improve end-to-end performance because agents are persistent - they'll eventually find what they need even with suboptimal tools. This makes traditional embedding evaluation metrics less useful for agentic systems.

For those starting from scratch, Colin recommends:

1. Build the simplest possible retrieval tool
2. Put an agent loop on top
3. Iterate based on what causes the most pain for users
4. Only move to quantitative evaluation once you've addressed obvious issues

I found it refreshing that Colin focused on specific examples of queries rather than abstract discussions of model architectures. As he put it, "Being a researcher is actually very similar to being a product person - you're working backwards from use cases and examples."

**When to use embedding models vs. simple search tools** While grep and find worked well for SWE-Bench's relatively small codebases, Colin identified several scenarios where embedding models become essential:

1. Searching large codebases
2. Retrieving from unstructured content like Slack messages or documentation
3. Searching across third-party code that models haven't memorized
4. Retrieving from non-text media like video recordings of user sessions

"If I was a human working on this use case, and I was a really persistent human that never got tired, would having this other search tool help me? If the answer is yes, then it's probably going to be useful for the agent."

Colin noted that SWE-Bench is somewhat artificial - its repositories are smaller than real-world codebases, and 90% of its problems take less than an hour for a good engineer to solve. In more complex environments, embedding models become increasingly valuable.

**Improving agentic retrieval systems** To enhance agentic retrieval, Colin recommends:

1. Adding re-rankers to embedding tools to improve precision and reduce token usage
2. Training specialized embedding models for different tasks (e.g., one for code, another for Slack messages)
3. Prompt-tuning tool schemas to guide agents toward efficient usage patterns
4. Creating hierarchical retrieval systems that summarize files and directories
5. Leveraging language server protocols as additional tools

One particularly effective technique is asynchronous pre-processing: "I've taken songs and used an LLM to create a dossier about each one. This simple pre-processing step took a totally non-working search system and turned it into something that works really well."

## Why aren't more people training great embedding models?

When asked what question people aren't asking enough, Colin highlighted the lack of expertise in training embedding models: "Very few people understand how to build and train good retrieval systems. It just confuses me why no one knows how to fine-tune really good embedding models."

He attributed this partly to the specialized nature of the skill and partly to data availability. For code, there's abundant data on GitHub, but most domains lack comparable resources. Additionally, the most talented engineers often prefer working on LLMs rather than embedding models.

***Key Takeaway:*** As agents become more capable, the quality of their tools becomes increasingly important. Even though agents can compensate for suboptimal tools through persistence, providing them with better retrieval mechanisms significantly improves their efficiency and capabilities.

**Final thoughts on the future of retrieval** Colin believes we're entering an era where the boundaries between traditional RAG and agentic systems are blurring. The ideal approach combines the strengths of both: the speed and efficiency of well-tuned embedding models with the persistence and course-correction of agents.

As these systems evolve, we'll likely see more specialized tools emerging for different retrieval contexts, along with more sophisticated pre-processing techniques that make retrieval more effective. The key is focusing on the specific problems you're trying to solve rather than getting caught up in architectural debates.

"Agents are getting radically smarter, but even Einstein preferred writing on paper instead of a stone tablet," Colin noted. "Yes, these agents are persistent, but you should give them whatever you can to improve the odds that they find what they're looking for."

---

**FAQs**

## What is agentic retrieval and how does it differ from traditional RAG?

Agentic retrieval is an approach where AI agents use tools like grep, find, or embedding models to search through code and other content. Unlike traditional RAG (Retrieval-Augmented Generation), which typically uses embedding databases and vector searches, agentic retrieval gives the agent direct control over the search process. This allows the agent to be persistent, try multiple search strategies, and course-correct when initial attempts fail. Traditional RAG is more rigid but can be faster and more efficient for certain use cases.

## Do agents make traditional RAG obsolete?

No, agents don't make traditional RAG obsolete—they complement it. The best approach is often to build agentic retrieval on top of your existing retrieval system by exposing your embedding models and search capabilities as tools that an agent can use. This combines the strengths of both approaches: the persistence and flexibility of agents with the efficiency and scalability of well-tuned embedding models.

Using simple tools like grep and find with agents offers several advantages:

* Iterative retrieval becomes much easier as agents can refine searches based on previous results
* Token budget management is simpler since old tool calls can be truncated and rerun if needed
* The system is easier to build and maintain without complex vector database dependencies
* Agents can course-correct when searches don't yield useful results by trying different approaches

## What are the limitations of using grep and find for retrieval?

While grep and find work well for certain scenarios, they have significant limitations:

* They don't scale well to very large codebases (millions of files)
* They're ineffective for searching through unstructured natural language content
* They work best with highly structured content like code that contains distinctive keywords
* They can be slower than optimized embedding-based searches for large datasets

## What's the ideal approach to retrieval for coding agents?

The best approach is often a hybrid system that combines:

1. An agentic loop that gives the agent control over the search process
2. Access to multiple search tools including grep, find, and embedding-based search
3. The ability to choose the most appropriate tool based on the specific search task
4. Course correction capabilities when initial searches don't yield useful results

## How should I evaluate agentic retrieval systems?

Start with a qualitative "vibe check" using 5-10 examples to understand how the system performs. Observe the agent's behavior, identify patterns in successes and failures, and develop an intuition for where improvements are needed. Only after this initial assessment should you move to quantitative end-to-end evaluations or specific evaluations of individual components like embedding tools. Remember that improving a single component (like an embedding model) may not necessarily improve the end-to-end performance if the agent is already persistent enough to overcome limitations.

## I already built a retrieval system with custom-trained embedding models. Should I replace it with agentic retrieval?

No, don't replace it—enhance it. Build agentic retrieval on top of your existing system by exposing your embedding models and search capabilities as tools that an agent can use. This gives you the best of both worlds: the quality and efficiency of your custom embeddings plus the persistence and flexibility of an agent.

## How can I improve my agentic retrieval system?

Focus on building better tools for your agent:

* Add re-rankers to your embedding tools to improve precision and reduce token usage
* Train different embedding models for different specific tasks
* Prompt-tune your tool schemas to help the agent use them effectively
* Consider hierarchical retrieval approaches like creating summaries of files or directories
* Add specialized tools for specific retrieval tasks (like searching commit history)

## How do memories work with agentic retrieval systems?

Memories in agentic systems can be implemented by adding tools that save and read memories. These memories can serve as a semantic cache that speeds up future searches by storing information about the codebase structure, relevant interfaces, or other insights gained during previous searches. This can significantly improve performance on similar tasks in the future.

## Why did embedding models not improve performance on SWE-Bench?

For the SWE-Bench coding evaluation, embedding models didn't significantly improve performance because:

1. The repositories were relatively small, making grep and find sufficient
2. The code was highly structured with distinctive keywords that made text-based search effective
3. The agent's persistence compensated for less sophisticated search tools
4. The tasks were relatively simple, typically solvable by a good engineer in under an hour

## This doesn't mean embedding models aren't valuable—they become essential for larger codebases, less structured content, or more complex retrieval tasks.

---

### Test yourself

1. What characteristics of code repos made grep win? Which of those characteristics show up in CodePipeline's domain?
2. Generalize the rule: predict, before measuring, when embeddings will lose to a sparse method. What signal would tell you?
3. What's the inverse — describe a corpus and query distribution where embeddings would *crush* grep, and explain why.

---

## Systematically Improving Your RAG

*Jason Liu · jxnl.co · 22 May 2024 · [https://jxnl.co/writing/2024/05/22/systematically-improving-your-rag/](https://jxnl.co/writing/2024/05/22/systematically-improving-your-rag/)*

> The playbook. The other four pieces tell you *why* the layers exist; this one tells you the order of operations for improving a real system. Two things to pull from this hardest: (1) synthetic Q→chunk pairs as the cheapest possible offline metric — without this you're guessing; (2) "use both full-text search and vector search" stated bluntly as table stakes. Notice how often the chapter headings are *measurement and feedback* rather than *new model* — that's the lesson.

# Systematically Improving Your RAG

This article explains how to make Retrieval-Augmented Generation (RAG) systems better. It's based on a talk I had with [Hamel](https://hamel.dev) and builds on other articles I've written about RAG. For a comprehensive understanding of RAG fundamentals, see my guide on [what RAG is](../../../11/07/what-is-retrieval-augmented-generation/).

In [RAG is More Than Just Embeddings](../../../../2023/09/17/rag-is-more-than-embeddings/), I talk about how RAG is more than just vector embeddings. This helps you understand RAG better. I also wrote [How to Build a Terrible RAG System](../../../01/07/inverted-thinking-rag/), where I show what not to do, which can help you learn good practices.

If you want to learn about how complex RAG systems can be, check out [Levels of RAG Complexity](../../../02/28/levels-of-complexity-rag-applications/). This article breaks down RAG into smaller parts, making it easier to understand. For quick tips on making your RAG system better, read [Low Hanging Fruit in RAG](../../11/low-hanging-fruit-for-rag-search/).

I also wrote about what I think will happen with RAG in the future in [Predictions for the Future of RAG](../../../06/05/predictions-for-the-future-of-rag/). This article talks about how RAG might be used to create reports in the future.

All these articles work together to give you a full guide on how to make RAG systems better. They offer useful tips for developers and companies who want to improve their systems. For additional improvement strategies, check out my [six tips for improving RAG](../../../11/04/how-to-improve-rag-applications-6-proven-strategies/) and insights on [RAG anti-patterns](../../../../2025/06/11/rag-anti-patterns-with-skylar-payne/). If you're interested in AI engineering in general, you might enjoy my talk at the [AI Engineer Summit](../../../../2023/11/02/ai-engineer-keynote-pydantic-is-all-you-need/). In this talk, I explain how tools like Pydantic can help with prompt engineering, which is useful for building RAG systems.

Through all these articles, I try to give you a complete view of RAG systems. I cover everything from basic ideas to advanced uses and future predictions. This should help you understand and do well in this fast-changing field.

By the end of this post, you'll understand my step-by-step approach to making RAG applications better for the companies I work with. We'll look at important areas like:

* Making fake questions and answers to quickly test how well your system works
* Using both full-text search and vector search together for the best results
* Setting up the right ways to get feedback from users about what you want to study
* Using grouping to find sets of questions that have problems, sorted by topics and abilities
* Building specific systems to improve abilities
* Constantly checking and testing as you get more real-world data

This step-by-step runbook shows how to incrementally improve the performance and utility of your RAG applications. Let's dive in and explore how to systematically improve your RAG systems.

## Start with Synthetic Data

I think the biggest mistake around improving the system is that most people are spending too much time on the actual synthesis without actually understanding whether or not the data is being retrieved correctly. To avoid this:

* Create synthetic questions for each text chunk in your database
* Use these questions to test your retrieval system
* Calculate precision and recall scores to establish a baseline
* Identify areas for improvement based on the baseline scores

What we should be finding with synthetic data is that synthetic data should just be around 97% recall precision. And synthetic data might just look like something very simple to begin with.

We might just say, for every text chunk, I want it to synthetically generate a set of questions that this text chunk answers. For those questions, can we retrieve those text chunks? And you might think the answer is always going to be yes. But I found in practice that when I was doing tests against essays, full text search and embeddings basically performed the same, except full text search was about 10 times faster. This approach is part of my broader [RAG flywheel strategy](../../../08/19/rag-flywheel/).

Whereas when I did the same experiment on pulling issues from a repository, it was the case that full text search got around 55% recall, and then embedding search got around 65% recall. And just knowing how challenging these questions are on the baseline is super important to figure out what kind of experimentation you need to perform better. This will give you a baseline to work with and help you identify areas for improvement. For a detailed breakdown of evaluation metrics, see my guide on [the only 6 RAG evaluations you need](../../../../2025/05/19/there-are-only-6-rag-evals/).

Extract and make searchable relevant metadata (e.g., date ranges, file names, ownership) to improve search results.

* Extract relevant metadata from your documents
* Include metadata in your search indexes
* Use query understanding to extract metadata from user queries
* Expand search queries with relevant metadata to improve results

For example, if someone asks, "What is the latest x, y, and z?" Text search will never get that answer. Semantic search will never get that answer.

You need to perform query understanding to extract date ranges. There will be some prompt engineering that needs to happen. For enterprise implementations, see my guide on [RAG enterprise process](../../../../2025/06/09/how-to-invest-in-ai-w-mcps-and-data-analytics/). That's the metadata, and being aware that there will be questions that people aren't answering because those filters can never be caught by full text search and semantic search.

And what this looks like in practice is if you ask the question, what are recent developments in the field, the search query is now expanded out to more terms. There's a date range where the language model has reasoned about what recent looks like for the research, and it's also decided that you should only be searching specific sources. If you don't do this, then you may not get trusted sources. You may be unable to figure out what recent means.

You'll need to do some query understanding to extract date ranges and include metadata in your search.

## Use Both Full-Text Search and Vector Search

Utilize both full-text search and vector search (embeddings) for retrieving relevant documents. Ideally, you should use a single database system to avoid synchronization issues.

* Implement both full-text search and vector search
* Test the performance of each method on your specific use case
* Consider using a single database system to store both types of data
* Evaluate the trade-offs between speed and recall for your application

In my experience, full-text search can be faster, but vector search can provide better recall.

What ended up being very complicated was if you have a single knowledge base, maybe that complexity is fine, because you have more configuration of each one.

But one of my clients who was doing construction data, they had to create separate indices per project, and now they just had this exploding array of different data sources that get in or out of sync. Like, maybe the database has an outage, and now the data is not in the database, but it's in another system. So if the embedding gets pulled up, then text is missing.

And this complex configuration becomes a huge pain. And so, for example, some tools are able to do all 3 in a single object. And so even if you had a lot of partitioned data sources, you can do full text search, embedding search, and write SQL against a single data object. And that has been really helpful, especially when you think about these examples where you want to find the latest. Now you can just do a full text search query and then order by date and have a between clause.

Test both and see what works best for your use case.

## Implement Clear User Feedback Mechanisms

Implement clear user feedback systems (e.g., thumbs up/down) to gather data on your system's performance and identify areas for improvement.

* Add user feedback mechanisms to your application
* Make sure the copy for these mechanisms clearly describes what you're measuring
* Ask specific questions like "Did we answer the question correctly?" instead of general ones like "How did we do?"
* Use the feedback data to identify areas for improvement and prioritize fixes

I find that it's important to build out these feedback mechanisms as soon as possible. And making sure that the copy of these feedback mechanisms explicitly describe what you're worried about.

Sometimes, we'll get a thumbs down even if the answer is correct, but they didn't like the tone. Or the answer was correct, but the latency was too high. Or it took too many hops.

This means we couldn't actually produce an evaluation dataset just by figuring out what was a thumbs up and a thumbs down. It was a lot of confounding variables. We had to change the copy to just "Did we answer the question correctly? Yes or no." We need to recognize that improvements in tone and improvements in latency will come eventually. But we needed the user feedback to build us that evaluation dataset.

Make sure the copy for these feedback mechanisms explicitly describes what you're worried about. This will help you isolate the specific issues users are facing.

## Cluster and Model Topics

Analyze user queries and feedback to identify topic clusters, capabilities, and areas of user dissatisfaction. This will help you prioritize improvements.

Why should we do this? Let me give you an example. I once worked with a company that provided a technical documentation search system. By clustering user queries, we identified two main issues:

1. Topic Clusters: A significant portion of user queries were related to a specific product feature that had recently been updated. However, our system was not retrieving the most up-to-date documentation for this feature, leading to confusion and frustration among users.
2. Capability Gaps: Another cluster of queries revealed that users were frequently asking for troubleshooting steps and error code explanations. While our system could retrieve relevant documentation, it struggled to provide direct, actionable answers to these types of questions.

Based on these insights, we prioritized updating the product feature documentation and implementing a feature to extract step-by-step instructions and error code explanations. These targeted improvements led to higher user satisfaction and reduced support requests.

Look for patterns like:

* Topic clusters: Are users asking about specific topics more than others? This could indicate a need for more content in those areas or better retrieval of existing content. I explore this concept further in my post on [RAG decomposition](../../../11/18/decomposing-rag-systems-to-identify-bottlenecks/) and [topics and capabilities](../../../06/29/art-of-looking-at-rag-data/).
* Capabilities: Are there types of questions your system categorically cannot answer? This could indicate a need for new features or capabilities, such as direct answer extraction, multi-document summarization, or domain-specific reasoning.

By continuously analyzing topic clusters and capability gaps, you can identify high-impact areas for improvement and allocate your resources more effectively. This data-driven approach to prioritization ensures that you're always working on the most critical issues affecting your users.

Once you have this in place, once you have these topics and these clusters, you can talk to domain experts for a couple of weeks to figure out what these categories are explicitly. Then, you can build out systems to tag that as data comes in.

In the same way that when you open up ChatGPT and make a conversation, it creates an automatic title in the corner. You can now do that for every question. As part of that capability, you can add the classification, such as what are the topics and what are the capabilities. Capabilities could include ownership and responsibility, fetching tables, fetching images, fetching documents only, no synthesis, compare and contrast, deadlines, and so on. For more on selecting the right tools and capabilities, see my post on [trade-offs in tool selection](../../../08/21/trade-off-tool-selection/).

You can then put this information into a tool like Amplitude or Sentry. This will give you a running stream of the types of queries people are asking, which can help you understand how to prioritize these capabilities and topics.

## Continuously Monitor and Experiment

Continuously monitor your system's performance and run experiments to test improvements.

* Set up monitoring and logging to track system performance over time
* Regularly review the data to identify trends and issues
* Design and run experiments to test potential improvements
* Measure the impact of changes on precision, recall, and other relevant metrics
* Implement changes that show significant improvements

This could include tweaking search parameters, adding metadata, or trying different embedding models. Measure the impact on precision and recall to see if the changes are worthwhile.

Once you now have these questions in place, you have your synthetic data set and a bunch of user data with ratings. This is where the real work begins when it comes to systematically improving your RAG.

The system will be running many clusters of topic modeling around the questions, modeling that against the thumbs up and thumbs down ratings to figure out what clusters are underperforming. It will then determine the count and probability of user dissatisfaction for each cluster.

The system will be doing this on a regular cadence, figuring out for what volume of questions and user satisfaction levels it should focus on improving these specific use cases.

What might happen is you onboard a new organization, and all of a sudden, those distributions shift because their use cases are different. That's when you can go in and say, "We onboarded these new clients, and they very much care about deadlines. We knew we decided not to service deadlines, but now we know this is a priority, as it went from 2% of questions asking about deadlines to 80%." You can then determine what kind of education or improvements can be done around that.

## Balance Latency and Performance

Finally, make informed decisions about trade-offs between system latency and search performance based on your specific use case and user requirements.

* Understand the latency and performance requirements for your application
* Measure the impact of different configurations on latency and performance
* Make trade-offs based on what's most important for your users
* Consider different requirements for different use cases (e.g., medical diagnosis vs. general search)

Here, this is where having the synthetic questions that test against will effectively answer that question. Because what we'll do is we'll run the query with and without this parent document retriever, and we will have a recall with and without that feature and the latency improvement of that feature.

And so now we'll be able to say, okay. Well, recall doubles. The latency increases by 20%, then a conversation can happen. Or, is that worth the investment? But if latency goes up double and the recall goes up 1%, again, it depends on, okay.

Well, if this is a medical diagnostic, maybe I do care that the 1% is included because the stakes are so high. But if it's for a doc page, maybe the increased latency will reduce in churn.

If you can improve recall by 1%, and the results are too complex, it's not worth deploying it in the future as well.

For example, if you're building a medical diagnostic tool, a slight increase in latency might be worth it for better recall. But if you're building a general-purpose search tool, faster results might be more important.

## Wrapping Up

This is was written based off of a 30 conversation with a client, so I know I'm skipping over many details and implementation details. Leave a comment and let me know and we can get into specifics.

## Want to learn more?

This was based on a 30-minute conversation, so I'm definitely skipping implementation details. The real breakthrough happens when you stop random improvements and start measuring what actually moves the needle:

[Free 6-Week RAG Email Course](https://dub.link/6wk-rag-email) [Full Course Breakdown](../../../../2025/01/24/systematically-improving-rag-applications/) [RAG FAQ](../../../10/26/faq-on-improving-rag-applications/)

### Test yourself

1. Of the seven improvements listed, which one would move the needle the most in the nearest production RAG system you touch? Justify in one sentence.
2. The synthetic-data trick: what's the cheapest possible version you could ship in your codebase tomorrow morning?
3. Jason centers metrics over model choice. What's the *one* metric you would instrument first, and what would the data unlock?

---

## Cross-cutting questions

These tie back across all five sources. No answer keys — work through them in your head on Kobo, then we'll talk on the next chat.

1. Write the three-line "what is dense vs sparse retrieval, and why do production systems use both" explanation you'd give a peer who has never thought about it. (Test: could you give it without using the word *embedding* in the first sentence?)
2. If you were starting a new RAG system tomorrow with no prior commitments, what's your *default first architecture* — be concrete: which retrieval components, which order, which evaluation harness? What would you measure first?
3. Where does **reranking** sit in this picture? Cohere's reranker, cross-encoders, fusion-style rerankers — based on what you've read, how would you describe what a reranker does, and why it's separated from initial retrieval?
4. **Setting up next week.** Which of these is the topic you most want to go one notch deeper on, and why?
   - **BM25 internals** — k1, b, length normalization, tuning trade-offs
   - **Reranker mechanics** — cross-encoders vs bi-encoders, when each pays off
   - **Graphiti / GraphRAG internals** — entity extraction, temporal model, traversal
   - **RAG evals as a discipline** — golden sets, recall@k, eval-driven iteration
