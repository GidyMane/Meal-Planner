import streamlit as st
from PIL import Image
import os
import tempfile
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from MealAgent.execution import MealPlannerAgent, AgentState, CurrentConversationInput
from langchain_core.messages import HumanMessage

# Load environment variables from .env file
load_dotenv()

# --- 0. INITIALIZE AGENT ---
@st.cache_resource
def initialize_agent():
    """Initialize the MealPlannerAgent with Gemini model"""
    # You'll need to set your GOOGLE_API_KEY in environment variables
    # or replace with your actual API key
    model = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0.7
    )
    agent = MealPlannerAgent(model)
    return agent.build_graph()

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="ChefGPT Luxe", page_icon="🥑", layout="wide")

# --- 2. STYLING (GLASSMORPHISM & CARDS) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Inter:wght@400;600&display=swap');
    .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    
    .navbar {
        display: flex; justify-content: space-between; align-items: center;
        background: rgba(255, 255, 255, 0.9); backdrop-filter: blur(10px);
        padding: 15px 50px; border-radius: 0 0 30px 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-bottom: 40px;
    }
    .nav-logo { font-family: 'Playfair Display', serif; font-size: 28px; color: #1e1e1e; }
    
    .main-card {
        background: rgba(255, 255, 255, 0.95);
        padding: 40px; border-radius: 25px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }
    .pill {
        display: inline-block; background: #ff4b4b; color: white;
        padding: 5px 15px; border-radius: 50px; margin: 5px;
        font-size: 0.8rem; font-weight: bold;
    }
    .store-item {
        color: #d9534f; font-weight: 600; font-style: italic;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. NAVBAR ---
st.markdown("""
    <div class="navbar">
        <div class="nav-logo">🍳 ChefGPT Luxe</div>
        <div style="display: flex; gap: 30px; font-weight: 600;">
            <span>Inventory</span><span>Recipes</span><span>Pro</span>
        </div>
    </div>
""", unsafe_allow_html=True)

# --- 4. APP STATE MANAGEMENT ---
if "step" not in st.session_state:
    st.session_state.step = "input"
if "thread_id" not in st.session_state:
    st.session_state.thread_id = "thread_1"
if "uploaded_image_path" not in st.session_state:
    st.session_state.uploaded_image_path = None
if "user_preferences" not in st.session_state:
    st.session_state.user_preferences = {}
if "clarification_data" not in st.session_state:
    st.session_state.clarification_data = None
if "recipe_data" not in st.session_state:
    st.session_state.recipe_data = None

def change_step(new_step):
    st.session_state.step = new_step

def save_uploaded_file(uploaded_file):
    """Save uploaded file to a temporary location and return path"""
    if uploaded_file is not None:
        # Create a temporary directory if it doesn't exist
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, uploaded_file.name)
        
        # Save the file
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        return file_path
    return None

# --- 5. MAIN PAGE: INPUT & UPLOAD ---
if st.session_state.step == "input":
    st.markdown("<h1 style='text-align: center; font-family: Playfair Display; font-size: 3.5rem;'>What's cooking today?</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 5, 1])
    
    with col2:
        with st.container(border=True):
            st.markdown("<div class='main-card'>", unsafe_allow_html=True)
            u_left, u_right = st.columns([1, 1.2])
            
            with u_left:
                st.markdown("### 📸 1. Your Ingredients")
                uploaded_file = st.file_uploader("Upload fridge photo", type=['jpg', 'png', 'jpeg'], label_visibility="collapsed")
                
                if uploaded_file:
                    img = Image.open(uploaded_file)
                    st.image(img, caption="Your Ingredients Photo", use_container_width=True)
                    # Save the file path
                    st.session_state.uploaded_image_path = save_uploaded_file(uploaded_file)
                    
                    # Show detected ingredients if available
                    if "detected_ingredients" in st.session_state and st.session_state.detected_ingredients:
                        st.success("✅ Ingredients detected!")
                        st.markdown(f"**{st.session_state.detected_ingredients}**")
                else:
                    st.info("Upload a photo to see the preview.")

            with u_right:
                st.markdown("### ✏️ 2. Preferences")
                dietary_instructions = st.text_area(
                    "Dietary instructions", 
                    placeholder="e.g. 'High protein, no dairy, use the chicken first.'", 
                    height=150,
                    key="dietary_instructions"
                )
                
                g1, g2 = st.columns(2)
                with g1: 
                    meal_style = st.selectbox("Style", ["Muscle Gain", "Weight Loss", "Quick Meal"], key="meal_style")
                with g2: 
                    meal_time = st.select_slider("Time", ["15m", "30m", "60m"], key="meal_time")

            st.write("---")
            if st.button("✨ Craft My Recipe", use_container_width=True, type="primary"):
                if uploaded_file and st.session_state.uploaded_image_path:
                    # Store preferences
                    st.session_state.user_preferences = {
                        "goal": meal_style,
                        "instructions": f"{dietary_instructions}. Time available: {meal_time}",
                        "images": [st.session_state.uploaded_image_path]
                    }
                    
                    # Initialize and run the agent
                    with st.spinner("🔍 Analyzing your ingredients..."):
                        try:
                            app = initialize_agent()
                            
                            # Create initial state
                            initial_state = AgentState(
                                current_conversation_input=CurrentConversationInput(
                                    goal=st.session_state.user_preferences["goal"],
                                    instructions=st.session_state.user_preferences["instructions"],
                                    images=st.session_state.user_preferences["images"]
                                )
                            )
                            
                            # Run the agent
                            config = {"configurable": {"thread_id": st.session_state.thread_id}}
                            result = app.invoke(initial_state, config)
                            
                            # Check if clarification is needed
                            if result.image_processing_output and result.image_processing_output.clarification_needed:
                                st.session_state.clarification_data = result.image_processing_output.clarification_question
                                change_step("clarify")
                            elif result.meal_recipe:
                                st.session_state.recipe_data = result.meal_recipe
                                change_step("recipe")
                            
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"An error occurred: {str(e)}")
                            st.exception(e)
                else:
                    st.warning("Please upload a photo first!")
            st.markdown("</div>", unsafe_allow_html=True)

# --- 6. CLARIFY STATE (INTERRUPT) ---
elif st.session_state.step == "clarify":
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 🧐 Quick Question")
        
        # Display the uploaded image
        if st.session_state.uploaded_image_path:
            st.image(st.session_state.uploaded_image_path, width=400)
        
        # Show clarification question from agent
        if st.session_state.clarification_data:
            question = st.session_state.clarification_data.question or "Could you provide more details about the ingredients?"
            st.info(f"**{question}**")
        
        clarification_response = st.text_input("Please clarify:", placeholder="e.g. They are Sweet Potatoes")
        
        if st.button("Generate Recipe →", use_container_width=True, type="primary"):
            if clarification_response:
                with st.spinner("🍳 Generating your recipe..."):
                    try:
                        app = initialize_agent()
                        config = {"configurable": {"thread_id": st.session_state.thread_id}}
                        
                        # Resume the agent with clarification
                        result = app.invoke(
                            {"text": clarification_response},
                            config
                        )
                        
                        if result.meal_recipe:
                            st.session_state.recipe_data = result.meal_recipe
                            change_step("recipe")
                            st.rerun()
                        
                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")
            else:
                st.warning("Please provide a clarification!")

# --- 7. RECIPE STATE (FINAL RESULT) ---
elif st.session_state.step == "recipe":
    recipe = st.session_state.recipe_data
    
    if recipe:
        st.markdown(f"<h1 style='text-align: center; font-family: Playfair Display;'>{recipe.meal_name or 'Your Custom Recipe'}</h1>", unsafe_allow_html=True)
        
        st.markdown('<div class="main-card">', unsafe_allow_html=True)
        r_left, r_right = st.columns([1, 1.5])
        
        with r_left:
            # Display uploaded image
            if st.session_state.uploaded_image_path:
                st.image(st.session_state.uploaded_image_path, use_container_width=True)
            
            # Meal description
            if recipe.meal_description:
                st.markdown(f"**{recipe.meal_description}**")
            
            st.markdown(f"**⏱️ Duration:** {recipe.duration_of_the_meal or 'N/A'}")
            
            st.markdown("### 📦 In Your Kitchen")
            if recipe.what_you_have:
                pills_html = ''.join([f'<span class="pill">{item}</span>' for item in recipe.what_you_have])
                st.markdown(pills_html, unsafe_allow_html=True)
            
            st.markdown("### 🛒 Grab from Store")
            if recipe.what_you_need_to_buy:
                store_items = ''.join([f"<p class='store-item'>• {item}</p>" for item in recipe.what_you_need_to_buy])
                st.markdown(store_items, unsafe_allow_html=True)

        with r_right:
            st.markdown("### 🍳 Cooking Instructions")
            if recipe.cooking_steps:
                for idx, step in enumerate(recipe.cooking_steps, 1):
                    st.write(f"**Step {idx}:** {step}")
            else:
                st.info("No cooking steps provided.")
            
            st.divider()
            
            # --- FUNCTIONAL BUTTONS ---
            b1, b2 = st.columns(2)
            with b1:
                if st.button("✅ Approve Recipe", use_container_width=True, type="primary"):
                    st.balloons()
                    st.success("Recipe saved to your meal plan!")
                    # You can add logic here to save to database or file
            with b2:
                if st.button("🔄 Generate Another", use_container_width=True):
                    with st.spinner("🍳 Creating a new recipe..."):
                        try:
                            app = initialize_agent()
                            config = {"configurable": {"thread_id": st.session_state.thread_id}}
                            
                            # Tell agent to regenerate
                            result = app.invoke(
                                HumanMessage(content="I have rejected this meal. Please generate another one"),
                                config
                            )
                            
                            if result.meal_recipe:
                                st.session_state.recipe_data = result.meal_recipe
                                st.rerun()
                                
                        except Exception as e:
                            st.error(f"An error occurred: {str(e)}")
            
            # Restart button
            if st.button("❌ Start Over", use_container_width=True):
                # Clear all session state
                st.session_state.step = "input"
                st.session_state.uploaded_image_path = None
                st.session_state.user_preferences = {}
                st.session_state.clarification_data = None
                st.session_state.recipe_data = None
                st.session_state.thread_id = f"thread_{st.session_state.get('counter', 0) + 1}"
                st.rerun()
                
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.error("No recipe data available. Please start over.")
        if st.button("← Back to Start"):
            change_step("input")
            st.rerun()