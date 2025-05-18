from google.cloud import bigquery
from typing import Optional, List, Dict
import json
import os
import google.generativeai as genai
from datetime import datetime

# Configure Google AI
GOOGLE_API_KEY = "YOUR_API_KEY"
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize BigQuery
client = bigquery.Client()

def chunk_text(text: str, chunk_size: int = 100) -> List[str]:
    """Split text into chunks of specified size."""
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

class ArticleChatbot:
    def __init__(self, article_id: str):
        """Initialize the chatbot with a specific article."""
        self.article_id = article_id
        self.article_data = self._get_article_data()
        self.model = genai.GenerativeModel('gemini_model') # chose the available Gemini model
        self.chat = self.model.start_chat(history=[])
        
        # Parse article data
        self.article_text = self.article_data.get('full_text', '')
        self.chunks = chunk_text(self.article_text)
        
        # Store conversation history
        self.conversation_history = []
        
        # Initialize chat with article context
        self._initialize_chat()
    
    def _initialize_chat(self):
        """Initialize the chat with article context."""
        # Get the most relevant context about the article
        context = self.get_relevant_context("What is this article about?")
        
        # Create a focused initial prompt
        initial_prompt = f"""You are an AI assistant helping users understand this article. Here is the relevant content:

{context}

Please help answer questions about this article. Use both the article content and our conversation history to provide relevant answers."""
        
        # Send initial context to the chat
        self.chat.send_message(initial_prompt)
        self.conversation_history.append(("system", initial_prompt))
    
    def _get_article_data(self) -> dict:
        """Retrieve article data from BigQuery."""
        try:
            query = """
            SELECT id, teaser_text, gemini_category, gemini_sub_category, title, full_text 
            FROM `project_id.dataset_id.table_id`
            WHERE id = @article_id
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("article_id", "STRING", self.article_id)
                ]
            )
            
            query_job = client.query(query, job_config=job_config)
            results = list(query_job)
            
            if not results:
                raise ValueError(f"Article with ID {self.article_id} not found")
                
            # Convert row to dict
            article_data = dict(results[0].items())
            return article_data
            
        except Exception as e:
            raise ValueError(f"Error retrieving article: {str(e)}")
    
    def get_relevant_context(self, query: str, top_k: int = 3) -> str:
        """Get relevant context from the article based on the query and conversation history."""
        query_terms = query.lower().split()
        relevant_chunks = []

        # Add conversation history to query terms
        for _, message in self.conversation_history[-3:]:  # Look at last 3 messages
            query_terms.extend(message.lower().split())

        for chunk in self.chunks:
            chunk_lower = chunk.lower()
            if any(term in chunk_lower for term in query_terms):
                # Clean up the text
                cleaned_chunk = chunk.replace('&quot;', '"').strip()
                relevant_chunks.append(cleaned_chunk)
                if len(relevant_chunks) >= top_k:
                    break

        if not relevant_chunks:
            return "No specific information found in the article."

        # Return the most relevant chunks
        return " ".join(relevant_chunks)
    
    def chat_with_article(self, user_input: str) -> str:
        """Process user input and return a response based on article content and conversation history."""
        try:
            # Get relevant context considering conversation history
            context = self.get_relevant_context(user_input)
            
            # Create prompt that includes context and conversation history
            conversation_context = "\n".join([f"{role}: {msg}" for role, msg in self.conversation_history[-3:]])
            
            prompt = f"""You are a helpful AI assistant. You have access to both the article content and our conversation history.

Previous conversation:
{conversation_context}

Article content: {context}

Question: {user_input}

Please provide a brief, direct answer that:
1. Answers the question in 1-2 sentences
2. Uses any available information (article, conversation history, or general knowledge)
3. Keeps the tone casual and natural
4. Focuses on the most important information
5. Don't mention where the information comes from

Your response:"""
            
            # Get response from the chat session
            response = self.chat.send_message(prompt)
            
            # Update conversation history
            self.conversation_history.append(("user", user_input))
            self.conversation_history.append(("assistant", response.text))
            
            return response.text
        except Exception as e:
            return self._handle_basic_response(user_input)
    
    def _handle_when_question(self) -> str:
        """Handle questions about when the article was published."""
        try:
            # Try to get date from article data
            date = self.article_data.get('publication_date', '')
            
            if date:
                # Format the date nicely
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                formatted_date = date_obj.strftime('%B %d, %Y')
                return f"Published on {formatted_date}"
            else:
                return "Publication date not available"
        except Exception as e:
            return "Error retrieving publication date"

    def _handle_basic_response(self, user_input: str) -> str:
        """Fallback method for basic responses when Google AI is not available."""
        user_input_lower = user_input.lower()

        if any(word in user_input_lower for word in ['what', 'tell me about']):
            return self._handle_what_question(user_input)
        elif any(word in user_input_lower for word in ['when', 'date', 'time']):
            return self._handle_when_question()
        elif any(word in user_input_lower for word in ['who', 'author']):
            return self._handle_who_question()
        elif any(word in user_input_lower for word in ['summary', 'overview', 'about']):
            return self._handle_summary_question()
        else:
            return self._handle_general_question(user_input)

    def _handle_what_question(self, question: str) -> str:
        """Handle 'what' questions about the article."""
        context = self.get_relevant_context(question)
        return context[:100] + '...' if len(context) > 100 else context

    def _handle_who_question(self) -> str:
        """Handle questions about who wrote the article."""
        if 'author' in self.article_data:
            return f"Author: {self.article_data['author']}"
        return "Author: N/A"

    def _handle_summary_question(self) -> str:
        """Handle requests for article summary."""
        summary = self.article_data.get('teaser_text', 'No summary available.')
        return summary[:100] + '...' if len(summary) > 100 else summary

    def _handle_general_question(self, question: str) -> str:
        """Handle general questions by finding relevant content."""
        context = self.get_relevant_context(question)
        return context[:100] + '...' if len(context) > 100 else context

def list_available_articles() -> List[dict]:
    """List all available articles in BigQuery."""
    try:
        query = """
        SELECT id, teaser_text, gemini_category, gemini_sub_category, title, full_text 
        FROM `aimedia25mun-322.BiteNews.article_metadata_chatbox`
      
        """
        
        query_job = client.query(query)
        results = list(query_job)
        
        articles = []
        for row in results:
            article_data = dict(row.items())
            articles.append({
                'id': article_data['id'],
                'title': article_data.get('title', 'Untitled'),
                'summary': article_data.get('teaser_text', 'No summary available'),
                'categories': {
                    'main': article_data.get('gemini_category', ''),
                    'sub': article_data.get('gemini_sub_category', '')
                }
            })
        
        return articles
    except Exception as e:
        print(f"Error listing articles: {str(e)}")
        return []

def main():
    # List available articles
    print("\n=== Starting Article Chatbot ===")
    print("Available articles:")
    articles = list_available_articles()
    for i, article in enumerate(articles, 1):
        print(f"{i}. {article['title']} (ID: {article['id']})")

    # Let user select an article
    while True:
        try:
            choice = input("\nEnter the number of the article you want to chat about (or 'q' to quit): ")
            if choice.lower() == 'q':
                return

            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(articles):
                selected_article = articles[choice_idx]
                print(f"\nSelected article:")
                print(f"ID: {selected_article['id']}")
                print(f"Title: {selected_article['title']}")
                print(f"Summary: {selected_article['summary']}")
                break
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a valid number.")

    # Initialize the chatbot with the selected article
    chatbot = ArticleChatbot(article_id=selected_article['id'])

    print(f"\nWelcome to the Article Chatbot! You're chatting about: {selected_article['title']}")
    print("Type 'quit' to exit or 'change' to select a different article.")

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == 'quit':
            break
        elif user_input.lower() == 'change':
            main()  # Restart the article selection process
            break

        response = chatbot.chat_with_article(user_input)
        print(f"\nBot: {response}")

if __name__ == "__main__":
    main()
