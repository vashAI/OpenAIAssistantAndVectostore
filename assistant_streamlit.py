import openai
import streamlit as st
import time
import io

class NamedBytesIO(io.BytesIO):
    def __init__(self, buffer, name):
        super().__init__(buffer)
        self.name = name

# Initialize the OpenAI API with your API key
openai.api_key = "YOUR OPENAI KEY"

# Function to wait for a response from the assistant
def wait_on_run(run, thread, client):
    while run.status == "queued" or run.status == "in_progress":
        run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id,
        )
        time.sleep(0.5)
    return run

# Function to send a message to the assistant and get a response
def send_message(content, thread, assistant_id, client):
    # Create a user message in the thread
    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=content
    )

    # Start a new run for the assistant
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id,
    )

    # Wait for the run to complete
    run = wait_on_run(run, thread, client)

    # Retrieve all messages from the thread
    messages = list(client.beta.threads.messages.list(thread_id=thread.id))
    
    # Return the latest message from the assistant
    return messages[0].content[0].text.value

# Streamlit UI
st.title("Assistant Chatbot")
st.write("Ask any question and have a continuous conversation!")
st.write("Upload a folder to be sent to the assistant.")

# Folder uploader using Streamlit file uploader
uploaded_files = st.file_uploader("Upload Folder Files", type=None, accept_multiple_files=True)
if len(uploaded_files) > 0 and "documents_uploaded" not in st.session_state.keys():

    st.session_state['documents_uploaded'] = True

    # Converting them into stream to be able to upload them to OpenAI Assistant / Vectorstore
    file_streams = []
    for file in uploaded_files:
        bytes_data = file.getvalue()
        file_streams.append(NamedBytesIO(bytes_data, file.name))

    client = openai.OpenAI(api_key=openai.api_key)
    st.session_state['client'] = client

    # Create a vector store caled "Financial Statements"
    vector_store = client.beta.vector_stores.create(name="Financial Statements")
    st.session_state['vector_store_id'] = vector_store.id
    
    # Use the upload and poll SDK helper to upload the files, add them to the vector store,
    # and poll the status of the file batch for completion.
    file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id, files=file_streams
    )

    assistant = client.beta.assistants.create(
        name="Document Analyser",
        instructions="You are an expert in Document Analysing. Answer questions briefly, in a sentence or less.",
        model="gpt-3.5-turbo",
        tools=[{"type": "file_search"}],
    )

    assistant = client.beta.assistants.update(
        assistant_id = assistant.id,
        tool_resources={"file_search": {"vector_store_ids": [st.session_state['vector_store_id']]}},
    )
    st.session_state['assistant_id'] = assistant.id

    thread = client.beta.threads.create()
    st.session_state['thread'] = thread

    st.session_state['chat_history'] = []  # Store chat history

if "documents_uploaded" in st.session_state.keys():
    client = st.session_state['client']
    assistant_id = st.session_state['assistant_id']
    thread = st.session_state['thread']

# Display the conversation history using st.chat_message
if "documents_uploaded" in st.session_state.keys() and st.session_state['chat_history']:
    for role, message in st.session_state['chat_history']:
        if role == "user":
            message1 = st.chat_message("user")
            message1.write(message)
        else:
            message2 = st.chat_message("assistant")
            message2.write(message)

# Collect user input using st.chat_input
user_input = st.chat_input("Type your question:")

# Once input is submitted
if user_input:
    # Display the user's message right away
    st.session_state['chat_history'].append(("user", user_input))
    
    # Re-render the chat history to show the user's message immediately
    message3 = st.chat_message("user")
    message3.write(user_input)

    # Get assistant's reply
    assistant_reply = send_message(user_input, thread, assistant_id, client)
    
    # Add assistant's reply to chat history
    st.session_state['chat_history'].append(("assistant", assistant_reply))

    # Display the assistant's reply
    message4 = st.chat_message("assistant")
    message4.write(assistant_reply)