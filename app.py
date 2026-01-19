import streamlit as st
from PIL import Image
import os
import tempfile
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from MealAgent.execution import MealPlannerAgent

# Load environment variables from .env file
load_dotenv()

# --- 0. INITIALIZE AGENT ---
@st.cache_resource
def initialize_agent():
    """Initialize the MealPlannerAgent with Gemini model"""
    api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found. Please check your .env file.")
    
    # Use the correct model name with version prefix
    model = ChatGoogleGenerativeAI(
        model="models/gemini-1.5-flash",  # Added "models/" prefix
        temperature=0.7,
        google_api_key=api_key
    )
    
    agent = MealPlannerAgent(model)
    return agent.build_graph()

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="ChefGPT Luxe", page_icon="🍳", layout="wide")

# --- 2. STYLING ---
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

# --- 4. STATE MANAGEMENT ---
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
if "detected_ingredients" not in st.session_state:
    st.session_state.detected_ingredients = None

def change_step(new_step):
    st.session_state.step = new_step

def save_uploaded_file(uploaded_file):
    """Save uploaded file to temporary location"""
    if uploaded_file is not None:
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return file_path
    return None

# --- 5. INPUT PAGE ---
if st.session_state.step == "input":
    st.markdown("<h1 style='text-align: center; font-family: Playfair Display; font-size: 3.5rem;'>What's cooking today?</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 5, 1])
    
    with col2:
        with st.container(border=True):
            st.markdown("<div class='main-card'>", unsafe_allow_html=True)
            
            # Single column layout - simpler UI
            st.markdown("### 📸 Upload Your Ingredients Photo")
            uploaded_file = st.file_uploader(
                "Choose an image", 
                type=['jpg', 'png', 'jpeg'],
                help="Upload a photo of your ingredients or fridge contents"
            )
            
            if uploaded_file:
                img = Image.open(uploaded_file)
                st.image(img, caption="Your Ingredients", width='stretch')
                st.session_state.uploaded_image_path = save_uploaded_file(uploaded_file)
                
                # Show detected ingredients if available
                if st.session_state.detected_ingredients:
                    st.success("✅ Ingredients detected!")
                    st.markdown(f"**{st.session_state.detected_ingredients}**")
            
            st.markdown("---")
            
            st.markdown("### ✏️ Your Preferences")
            
            # Instructions text area
            dietary_instructions = st.text_area(
                "Dietary instructions or preferences", 
                placeholder="e.g. 'High protein, no dairy, use the chicken first, vegetarian, etc.'", 
                height=120,
                key="dietary_instructions"
            )
            
            # Two columns for style and time
            pref1, pref2 = st.columns(2)
            
            with pref1:
                meal_style = st.selectbox(
                    "Meal Style", 
                    ["Balanced", "Muscle Gain", "Weight Loss", "Quick Meal", "Keto", "Vegan", "Low Carb"],
                    key="meal_style"
                )
            
            with pref2:
                meal_time = st.number_input(
                    "Cooking Time (minutes)", 
                    min_value=1, 
                    value=30, 
                    step=1,
                    key="meal_time",
                    help="How much time do you have to cook? Enter any number."
                )
            
            st.markdown("---")
            
            # Generate button
            if st.button("✨ Generate Recipe", width='stretch', type="primary"):
                if uploaded_file and st.session_state.uploaded_image_path:
                    st.session_state.user_preferences = {
                        "goal": meal_style,
                        "instructions": f"{dietary_instructions}. Time available: {meal_time} minutes",
                        "images": [st.session_state.uploaded_image_path]
                    }
                    
                    with st.spinner("🔍 Analyzing your ingredients..."):
                        try:
                            app = initialize_agent()
                            
                            # Create initial state as dictionary (LangGraph requirement)
                            initial_state = {
                                "current_conversation_input": {
                                    "goal": st.session_state.user_preferences["goal"],
                                    "instructions": st.session_state.user_preferences["instructions"],
                                    "images": st.session_state.user_preferences["images"]
                                }
                            }
                            
                            config = {"configurable": {"thread_id": st.session_state.thread_id}}
                            result = app.invoke(initial_state, config)
                            
                            # Handle dict or object response
                            if not isinstance(result, dict):
                                result = result.model_dump() if hasattr(result, 'model_dump') else result.__dict__
                            
                            # Store detected ingredients
                            if "image_processing_output" in result and result["image_processing_output"]:
                                img_output = result["image_processing_output"]
                                if isinstance(img_output, dict):
                                    detected = f"{img_output.get('image_name', 'Ingredients')}: {img_output.get('image_description', '')}"
                                    st.session_state.detected_ingredients = detected
                                    
                                    if img_output.get("clarification_needed"):
                                        st.session_state.clarification_data = img_output.get("clarification_question")
                                        change_step("clarify")
                                        st.rerun()
                                else:
                                    detected = f"{img_output.image_name}: {img_output.image_description}"
                                    st.session_state.detected_ingredients = detected
                                    
                                    if img_output.clarification_needed:
                                        st.session_state.clarification_data = img_output.clarification_question
                                        change_step("clarify")
                                        st.rerun()
                            
                            # Check for recipe
                            if "meal_recipe" in result and result["meal_recipe"]:
                                st.session_state.recipe_data = result["meal_recipe"]
                                change_step("recipe")
                                st.rerun()
                            
                        except Exception as e:
                            st.error(f"⚠️ Error: {str(e)}")
                            if "RESOURCE_EXHAUSTED" in str(e):
                                st.warning("🔄 API quota exceeded. Please wait a moment and try again, or switch to gemini-1.5-pro in the code.")
                else:
                    st.warning("📷 Please upload a photo first!")
            
            st.markdown("</div>", unsafe_allow_html=True)

# --- 6. CLARIFY PAGE ---
elif st.session_state.step == "clarify":
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 🧐 Quick Question")
        
        if st.session_state.uploaded_image_path:
            st.image(st.session_state.uploaded_image_path, width=400)
        
        if st.session_state.detected_ingredients:
            st.info(f"**Detected:** {st.session_state.detected_ingredients}")
        
        if st.session_state.clarification_data:
            if isinstance(st.session_state.clarification_data, dict):
                question = st.session_state.clarification_data.get("question", "Could you provide more details?")
            else:
                question = st.session_state.clarification_data.question if hasattr(st.session_state.clarification_data, "question") else "Could you provide more details?"
            st.warning(f"**{question}**")
        
        clarification_response = st.text_input("Your answer:", placeholder="e.g. They are Sweet Potatoes")
        
        if st.button("Generate Recipe →", width='stretch', type="primary"):
            if clarification_response:
                with st.spinner("🍳 Generating your recipe..."):
                    try:
                        app = initialize_agent()
                        config = {"configurable": {"thread_id": st.session_state.thread_id}}
                        
                        result = app.invoke({"text": clarification_response}, config)
                        
                        if not isinstance(result, dict):
                            result = result.model_dump() if hasattr(result, 'model_dump') else result.__dict__
                        
                        if "meal_recipe" in result and result["meal_recipe"]:
                            st.session_state.recipe_data = result["meal_recipe"]
                            change_step("recipe")
                            st.rerun()
                        
                    except Exception as e:
                        st.error(f"⚠️ Error: {str(e)}")
            else:
                st.warning("Please provide an answer!")

# --- 7. RECIPE PAGE ---
elif st.session_state.step == "recipe":
    recipe = st.session_state.recipe_data
    
    # Handle dict or object
    if isinstance(recipe, dict):
        meal_name = recipe.get("meal_name", "Your Custom Recipe")
        meal_description = recipe.get("meal_description")
        duration = recipe.get("duration_of_the_meal", "N/A")
        what_you_have = recipe.get("what_you_have", [])
        what_you_need = recipe.get("what_you_need_to_buy", [])
        cooking_steps = recipe.get("cooking_steps", [])
    else:
        meal_name = recipe.meal_name or "Your Custom Recipe"
        meal_description = recipe.meal_description
        duration = recipe.duration_of_the_meal or "N/A"
        what_you_have = recipe.what_you_have or []
        what_you_need = recipe.what_you_need_to_buy or []
        cooking_steps = recipe.cooking_steps or []
    
    if recipe:
        st.markdown(f"<h1 style='text-align: center; font-family: Playfair Display;'>{meal_name}</h1>", unsafe_allow_html=True)
        
        st.markdown('<div class="main-card">', unsafe_allow_html=True)
        r_left, r_right = st.columns([1, 1.5])
        
        with r_left:
            if st.session_state.uploaded_image_path:
                st.image(st.session_state.uploaded_image_path, width='stretch')
            
            if meal_description:
                st.markdown(f"*{meal_description}*")
            
            st.markdown(f"**⏱️ Duration:** {duration}")
            
            st.markdown("### 📦 In Your Kitchen")
            if what_you_have:
                pills_html = ''.join([f'<span class="pill">{item}</span>' for item in what_you_have])
                st.markdown(pills_html, unsafe_allow_html=True)
            else:
                st.info("Using ingredients from your photo")
            
            st.markdown("### 🛒 Shopping List")
            if what_you_need:
                store_items = ''.join([f"<p class='store-item'>• {item}</p>" for item in what_you_need])
                st.markdown(store_items, unsafe_allow_html=True)
            else:
                st.success("✅ You have everything!")

        with r_right:
            st.markdown("### 🍳 Cooking Instructions")
            if cooking_steps:
                for idx, step in enumerate(cooking_steps, 1):
                    st.write(f"**Step {idx}:** {step}")
            else:
                st.info("No cooking steps provided.")
            
            st.divider()
            
            b1, b2, b3 = st.columns(3)
            
            with b1:
                if st.button("✅ Save Recipe", width='stretch', type="primary"):
                    st.balloons()
                    st.success("Recipe saved!")
            
            with b2:
                if st.button("🔄 Try Different", width='stretch'):
                    with st.spinner("Creating new recipe..."):
                        try:
                            app = initialize_agent()
                            
                            new_state = {
                                "current_conversation_input": {
                                    "goal": st.session_state.user_preferences["goal"],
                                    "instructions": st.session_state.user_preferences["instructions"] + " Create a completely different recipe.",
                                    "images": st.session_state.user_preferences["images"]
                                }
                            }
                            
                            new_thread = f"thread_{st.session_state.get('counter', 0) + 1}"
                            config = {"configurable": {"thread_id": new_thread}}
                            
                            result = app.invoke(new_state, config)
                            
                            if not isinstance(result, dict):
                                result = result.model_dump() if hasattr(result, 'model_dump') else result.__dict__
                            
                            if "meal_recipe" in result and result["meal_recipe"]:
                                st.session_state.recipe_data = result["meal_recipe"]
                                st.session_state.counter = st.session_state.get('counter', 0) + 1
                                st.rerun()
                                
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
            
            with b3:
                if st.button("🏠 Start Over", width='stretch'):
                    st.session_state.step = "input"
                    st.session_state.uploaded_image_path = None
                    st.session_state.user_preferences = {}
                    st.session_state.clarification_data = None
                    st.session_state.recipe_data = None
                    st.session_state.detected_ingredients = None
                    st.session_state.thread_id = f"thread_{st.session_state.get('counter', 0) + 1}"
                    st.rerun()
                
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.error("No recipe available.")
        if st.button("← Back"):
            change_step("input")
            st.rerun()