# states
from typing import List, Dict, Any, Optional, Annotated, Union, Sequence
from pydantic import BaseModel, Field
import operator
from langchain_core.messages import HumanMessage, BaseMessage, SystemMessage, AIMessage
# define any util functions here
import glob as gl
import base64
import datetime
from langgraph.types import interrupt, Command

from utils import logger


class Message(BaseModel):
    role: str  # e.g., 'Human', 'AI', 'System'
    content: str

class CurrentConversationInput(BaseModel):
    goal: Optional[str] = None
    instructions: Optional[str] = None
    images: Optional[List[str]] = None

class Clarification(BaseModel):
    question: Optional[str] = None

class ImageProcessingOutput(BaseModel):
    image_name: Optional[str] = None
    image_description: Optional[str] = None
    clarification_needed: Optional[bool] = None
    clarification_question: Optional[Clarification] = None

class Ingredient(BaseModel):
    ingredient_name: Optional[str] = None

class MealRecipe(BaseModel):
    meal_name: Optional[str] = None
    meal_description: Optional[str] = None
    ingredients_list: Optional[List[Ingredient]] = None
    what_you_have: Optional[List[str]] = None
    what_you_need_to_buy: Optional[List[str]] = None
    duration_of_the_meal: Optional[str] = None
    cooking_steps: Optional[List[str]] = Field(
        default_factory=list,
        description="Step-by-step instructions on how to prepare the meal"
    )
    approve: Optional[bool] = None


class ExecutionTime(BaseModel):
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    execution_time: Optional[str] = None

class AgentState(BaseModel):
    messages: Annotated[Sequence[BaseMessage], operator.add] = Field(default_factory=list)
    current_conversation_input: Optional[CurrentConversationInput] = None
    image_processing_output: Optional[ImageProcessingOutput] = Field(default_factory=ImageProcessingOutput)
    meal_recipe: Optional[MealRecipe] = None
    errors: List[str] = Field(default_factory=list)
    retry_policy: int = 2
    clarification: Optional[Clarification] = None
    need_human: bool = False
    execution_time: Optional[ExecutionTime] = Field(default_factory=ExecutionTime)
    current_node_name: Optional[str] = None


class MealPlannerAgent:

    def __init__(self, model):
        self.model = model
        self.logger = logger.bind(node="MealPlannerAgent", request_id="main")


    def generate_image_blocks_from_path(self, path: str) -> dict:
        """Generate image block for LLM from file path"""
        self.logger.info(f"Generating image block from path: {path}")
        try:
            with open(path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")
                self.logger.info("Base64 encoding successful")
                return {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
        except Exception as e:
            self.logger.error(f"Failed to read image: {e}")
            raise

    def process_images(self, state: AgentState) -> AgentState:
        """Process uploaded images to identify ingredients"""
        self.logger.info("Processing images node")
        state.current_node_name = "process_images"

        if not state.execution_time:
            state.execution_time = ExecutionTime()
        state.execution_time.start_time = str(datetime.datetime.now())

        if not state.current_conversation_input or not state.current_conversation_input.images:
            state.errors.append("No images provided")
            return state

        images = state.current_conversation_input.images
        llm_with_structured_output = self.model.with_structured_output(ImageProcessingOutput)

        # Generate the image content blocks
        image_blocks = [
            self.generate_image_blocks_from_path(image)
            for image in images
        ]

        system_prompt = SystemMessage(content="""
You are a meal-planning assistant with strong visual understanding skills.

Your role is to analyze images related to food, meals, and cooking ingredients.
Most images will be photos of ingredients, prepared meals, or food items.

Your task is to accurately understand what is shown in each image, describe it clearly,
and determine whether additional clarification from the user is required.

IMPORTANT: Only set clarification_needed to True if the image is genuinely unclear,
blurry, or ambiguous. For most clear photos, you should be confident in your assessment.
""")

        human_message = HumanMessage(content=[
            {
                "type": "text",
                "text": """
Analyze the provided image(s).

Based on what you can see, return:
- The name of the main ingredient(s) or meal shown (if identifiable)
- A brief description of what the image contains
- Whether clarification from the user is needed

If the image is clear and you can identify the ingredients with confidence,
set clarification_needed to false.

If the image is unclear, incomplete, or could represent multiple things,
set clarification_needed to true and ask a clear, specific question
to help identify the meal or ingredients.
"""
            },
            *image_blocks
        ])

        current_messages = state.messages + [system_prompt, human_message]

        try:
            output = llm_with_structured_output.invoke(current_messages)
            state.image_processing_output = output
            state.messages = current_messages
            self.logger.info(f"Image processing successful. Clarification needed: {output.clarification_needed}")
        except Exception as e:
            self.logger.error(f"Image processing failed: {e}")
            state.errors.append(str(e))

        return state


    def image_clarification_node(self, state: AgentState) -> AgentState:
        """Handle clarification requests - not used in Streamlit flow"""
        self.logger.info("Image clarification node (skipped in Streamlit)")
        # In Streamlit, we handle this in the UI
        return state


    def decision_node(self, state: AgentState) -> str:
        """Decide whether clarification is needed or we can proceed to recipe generation"""
        self.logger.info("Decision node")
        
        if state.image_processing_output and state.image_processing_output.clarification_needed:
            self.logger.info("Clarification needed - routing to clarification")
            return "clarify"
        else:
            self.logger.info("No clarification needed - routing to recipe generation")
            return "generate_meal_recipe"


    def generate_meal_recipe(self, state: AgentState) -> AgentState:
        """Generate meal recipe based on identified ingredients"""
        self.logger.info("Generating meal recipe")
        
        # Build inventory string
        if state.image_processing_output:
            if state.image_processing_output.image_name:
                inventory_str = f"{state.image_processing_output.image_name}: {state.image_processing_output.image_description or 'detected in image'}"
            else:
                inventory_str = state.image_processing_output.image_description or "Various ingredients detected"
        else:
            inventory_str = "Ingredients from uploaded image"

        llm_chef = self.model.with_structured_output(MealRecipe)

        system_prompt = SystemMessage(content="""
You are a professional Resourceful Chef with expertise in creating delicious, practical meal plans.

Your goal is to suggest ONE complete meal plan based on the ingredients provided.

CRITICAL REQUIREMENTS:
1. Provide clear, step-by-step cooking instructions in the 'cooking_steps' field
2. Each step should be actionable and specific
3. List items in 'what_you_have' for ingredients detected in the image
4. List items in 'what_you_need_to_buy' for essential missing ingredients
5. Ensure the recipe fits the user's time constraints and dietary preferences
6. Make the meal name appealing and descriptive
7. Provide a brief but enticing meal description

The recipe should be:
- Practical and achievable
- Delicious and nutritious
- Aligned with user preferences
- Time-appropriate
""")

        goal = state.current_conversation_input.goal if state.current_conversation_input else "Balanced meal"
        instructions = state.current_conversation_input.instructions if state.current_conversation_input else ""

        human_prompt = f"""
User Goal: {goal}
Extra Instructions: {instructions}

Inventory detected in photos:
{inventory_str}

Please create a complete meal recipe that:
1. Uses the ingredients we have
2. Suggests what to buy (keep it minimal)
3. Provides detailed cooking steps
4. Matches the user's preferences and time constraints
"""

        try:
            recipe = llm_chef.invoke([system_prompt, HumanMessage(content=human_prompt)])
            state.meal_recipe = recipe
            
            # Ensure cooking_steps is not empty
            if not recipe.cooking_steps or len(recipe.cooking_steps) == 0:
                self.logger.warning("Recipe generated without cooking steps, adding default")
                recipe.cooking_steps = [
                    "Prepare all ingredients by washing and chopping as needed",
                    "Follow standard cooking procedures for the main ingredients",
                    "Season to taste and serve when ready"
                ]
            
            self.logger.info(f"Recipe generated successfully: {recipe.meal_name}")
        except Exception as e:
            self.logger.error(f"Recipe generation failed: {e}")
            state.errors.append(f"Chef Error: {str(e)}")

        return state


    def regenerate_meal(self, state: AgentState) -> str:
        """Decide if we should regenerate or end - not used in Streamlit"""
        self.logger.info("Regenerate meal decision")
        # In Streamlit, we handle regeneration through the UI
        return "END"


    def build_graph(self):
        """Build the LangGraph workflow"""
        from langgraph.graph import StateGraph, START, END
        from langgraph.checkpoint.memory import MemorySaver
        
        workflow = StateGraph(AgentState)

        # Add Nodes
        workflow.add_node("process_images", self.process_images)
        workflow.add_node("generate_meal_recipe", self.generate_meal_recipe)

        # Define Edges
        workflow.add_edge(START, "process_images")

        # Conditional edge based on clarification need
        workflow.add_conditional_edges(
            "process_images",
            self.decision_node,
            {
                "clarify": END,  # In Streamlit, we end here and handle in UI
                "generate_meal_recipe": "generate_meal_recipe"
            }
        )

        # After recipe generation, we're done
        workflow.add_edge("generate_meal_recipe", END)

        # Compile with checkpointer for state persistence
        app = workflow.compile(checkpointer=MemorySaver())

        return app