from nicegui import ui, events, app
from dataclasses import dataclass, field
from typing import Dict, Optional
import uuid
import os
from pathlib import Path

# Directory to store uploaded models
UPLOAD_DIR = Path(__file__).parent / 'uploaded_models'
UPLOAD_DIR.mkdir(exist_ok=True)

# Serve uploaded models as static files
app.add_static_files('/models', str(UPLOAD_DIR))


@dataclass
class UploadedModel:
    """Represents an uploaded 3D model"""
    id: str
    name: str
    filename: str
    url: str  # URL to access the model


@dataclass
class SceneObject:
    """Represents an object in the 3D scene"""
    id: str
    name: str
    obj_type: str
    obj: any  # The actual NiceGUI scene object
    nicegui_id: str = ''  # Internal NiceGUI object ID for click detection
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    scale_z: float = 1.0
    rot_x: float = 0.0  # Rotation in degrees
    rot_y: float = 0.0
    rot_z: float = 0.0
    color: str = '#4488ff'
    model_id: Optional[str] = None  # Reference to uploaded model if applicable


class SceneBuilder:
    """3D Scene Builder Application"""
    
    def __init__(self):
        self.objects: Dict[str, SceneObject] = {}
        self.uploaded_models: Dict[str, UploadedModel] = {}
        self.selected_object: Optional[str] = None
        self.scene = None
        self.object_list = None
        self.property_panel = None
        self.model_list = None
        self.object_counter = 0
        self.model_counter = 0
        self._drag_selected = False  # Flag to prevent click from clearing drag selection
        
        # Load existing models from upload directory
        self._load_existing_models()
    
    def _load_existing_models(self):
        """Load models that were previously uploaded"""
        for file in UPLOAD_DIR.glob('*.glb'):
            model_id = str(uuid.uuid4())[:8]
            self.model_counter += 1
            self.uploaded_models[model_id] = UploadedModel(
                id=model_id,
                name=file.stem,
                filename=file.name,
                url=f'/models/{file.name}'
            )
        
    def create_ui(self):
        """Create the main UI layout"""
        ui.dark_mode().enable()
        
        with ui.header().classes('bg-primary'):
            ui.label('3D Scene Builder').classes('text-h5 text-white')
            ui.space()
            with ui.row():
                ui.button('Clear Scene', on_click=self.clear_scene, icon='delete_sweep').props('flat color=white')
        
        with ui.row().classes('w-full h-screen'):
            # Left sidebar - Object creation
            with ui.card().classes('w-64 h-full'):
                ui.label('Add Objects').classes('text-h6')
                ui.separator()
                
                with ui.column().classes('w-full gap-2'):
                    ui.button('Box', on_click=lambda: self.add_object('box'), icon='check_box_outline_blank').classes('w-full')
                    ui.button('Sphere', on_click=lambda: self.add_object('sphere'), icon='circle').classes('w-full')
                    ui.button('Cylinder', on_click=lambda: self.add_object('cylinder'), icon='panorama_vertical').classes('w-full')
                    ui.button('Cone', on_click=lambda: self.add_object('cone'), icon='change_history').classes('w-full')
                    ui.button('Torus', on_click=lambda: self.add_object('torus'), icon='radio_button_unchecked').classes('w-full')
                    ui.button('Ring', on_click=lambda: self.add_object('ring'), icon='trip_origin').classes('w-full')
                
                ui.separator().classes('my-4')
                
                # Model upload section
                ui.label('Upload 3D Models').classes('text-h6')
                ui.upload(
                    label='Upload GLB',
                    on_upload=self.handle_model_upload,
                    on_rejected=lambda: ui.notify('Only .glb files allowed!'),
                    auto_upload=True,
                    max_file_size=50_000_000  # 50MB limit
                ).props('accept=.glb').classes('w-full')
                
                ui.separator().classes('my-4')
                ui.label('Model Library').classes('text-h6')
                self.model_list = ui.column().classes('w-full gap-1')
                self.update_model_list()
                
                ui.separator().classes('my-4')
                ui.label('Objects in Scene').classes('text-h6')
                self.object_list = ui.column().classes('w-full gap-1')
            
            # Center - 3D Scene
            with ui.card().classes('flex-grow h-full'):
                with ui.scene(
                    width=800, 
                    height=600,
                    drag_constraints='',
                    on_click=self.handle_click,
                    on_drag_start=self.handle_drag_start,
                    on_drag_end=self.handle_drag_end,
                ).classes('w-full') as self.scene:
                    # Add grid and axis helpers
                    self.scene.spot_light()
                    
            # Right sidebar - Properties
            with ui.card().classes('w-72 h-full'):
                ui.label('Properties').classes('text-h6')
                ui.separator()
                self.property_panel = ui.column().classes('w-full gap-2')
                self.update_property_panel()
    
    def add_object(self, obj_type: str):
        """Add a new object to the scene"""
        self.object_counter += 1
        obj_id = str(uuid.uuid4())[:8]
        name = f"{obj_type}_{self.object_counter}"
        
        # Create the scene object
        if obj_type == 'box':
            obj = self.scene.box(1, 1, 1)
        elif obj_type == 'sphere':
            obj = self.scene.sphere(0.5)
        elif obj_type == 'cylinder':
            obj = self.scene.cylinder(0.5, 1)
        elif obj_type == 'cone':
            obj = self.scene.cylinder(0.5, 0, 1)  # Cone is a cylinder with top radius 0
        elif obj_type == 'torus':
            obj = self.scene.torus(0.5, 0.15)
        elif obj_type == 'ring':
            obj = self.scene.ring(0.3, 0.5)
        elif obj_type.startswith('model:'):
            # Load a GLTF model
            model_id = obj_type.split(':', 1)[1]
            if model_id not in self.uploaded_models:
                ui.notify('Model not found!')
                return
            model = self.uploaded_models[model_id]
            obj = self.scene.gltf(model.url)
            name = f"{model.name}_{self.object_counter}"
        else:
            return
        
        # Configure the object
        color = '#4488ff'
        if not obj_type.startswith('model:'):
            obj.with_name(obj_id).material(color).draggable()
        else:
            obj.with_name(obj_id).draggable()
        
        # Store object data
        model_id_ref = obj_type.split(':', 1)[1] if obj_type.startswith('model:') else None
        scene_obj = SceneObject(
            id=obj_id,
            name=name,
            obj_type=obj_type,
            obj=obj,
            nicegui_id=obj.id,  # Store internal NiceGUI ID for click detection
            color=color,
            model_id=model_id_ref
        )
        self.objects[obj_id] = scene_obj
        
        # Select the new object
        self.select_object(obj_id)
        self.update_object_list()
        ui.notify(f'Added {name}')
    
    def remove_object(self, obj_id: str):
        """Remove an object from the scene"""
        if obj_id in self.objects:
            scene_obj = self.objects[obj_id]
            scene_obj.obj.delete()
            del self.objects[obj_id]
            
            if self.selected_object == obj_id:
                self.selected_object = None
                self.update_property_panel()
            
            self.update_object_list()
            ui.notify(f'Removed {scene_obj.name}')
    
    def select_object(self, obj_id: Optional[str]):
        """Select an object"""
        self.selected_object = obj_id
        self.update_property_panel()
        self.update_object_list()
        
        # Visual feedback (only for non-model objects)
        for oid, scene_obj in self.objects.items():
            if not scene_obj.obj_type.startswith('model:'):
                if oid == obj_id:
                    scene_obj.obj.material('#ffaa00')  # Highlight selected
                else:
                    scene_obj.obj.material(scene_obj.color)
    
    def handle_click(self, e: events.SceneClickEventArguments):
        """Handle click on the scene"""
        # If we just selected via drag, don't let click override
        if self._drag_selected:
            self._drag_selected = False
            return
            
        if e.hits:
            # Search all hits for a matching object
            for hit in e.hits:
                obj_id = self._find_object_by_event(hit.object_name, hit.object_id)
                if obj_id:
                    self.select_object(obj_id)
                    return
            # No match found - only deselect if clicking empty space
            self.select_object(None)
        else:
            self.select_object(None)
    
    def _find_object_by_event(self, object_name: str, object_id: str) -> Optional[str]:
        """Find our object ID from event data (name or NiceGUI internal ID)"""
        # Check by object_name first (our custom ID)
        if object_name and object_name in self.objects:
            return object_name
        # Check by NiceGUI internal ID (for GLTF models)
        # Also check if the object_id starts with our ID (child meshes)
        for obj_id, scene_obj in self.objects.items():
            if object_id == scene_obj.nicegui_id:
                return obj_id
            # For GLTF models, child mesh IDs often start with parent ID
            if scene_obj.obj_type.startswith('model:') and object_id and scene_obj.nicegui_id:
                if object_id.startswith(scene_obj.nicegui_id):
                    return obj_id
        return None
    
    def handle_drag_start(self, e: events.SceneDragEventArguments):
        """Handle when an object starts being dragged - select it"""
        obj_id = self._find_object_by_event(e.object_name, e.object_id)
        if obj_id:
            self._drag_selected = True  # Prevent click from clearing this
            self.select_object(obj_id)
    
    def handle_drag_end(self, e: events.SceneDragEventArguments):
        """Handle when an object is dragged"""
        obj_id = self._find_object_by_event(e.object_name, e.object_id)
        if obj_id:
            scene_obj = self.objects[obj_id]
            scene_obj.x = e.x
            scene_obj.y = e.y
            scene_obj.z = e.z
            self.update_property_panel()
    
    def update_object(self, obj_id: str):
        """Update an object's transform based on stored values"""
        if obj_id not in self.objects:
            return
        
        scene_obj = self.objects[obj_id]
        scene_obj.obj.move(scene_obj.x, scene_obj.y, scene_obj.z)
        scene_obj.obj.scale(scene_obj.scale_x, scene_obj.scale_y, scene_obj.scale_z)
        scene_obj.obj.rotate(scene_obj.rot_x, scene_obj.rot_y, scene_obj.rot_z)
        # Only apply material to non-model objects
        if not scene_obj.obj_type.startswith('model:'):
            scene_obj.obj.material(scene_obj.color if obj_id != self.selected_object else '#ffaa00')
    
    def update_object_list(self):
        """Update the list of objects in the sidebar"""
        self.object_list.clear()
        
        with self.object_list:
            for obj_id, scene_obj in self.objects.items():
                is_selected = obj_id == self.selected_object
                with ui.row().classes('w-full items-center gap-1'):
                    ui.button(
                        scene_obj.name,
                        on_click=lambda o=obj_id: self.select_object(o)
                    ).classes('flex-grow').props(
                        'flat' if not is_selected else 'color=primary'
                    )
                    ui.button(
                        icon='delete',
                        on_click=lambda o=obj_id: self.remove_object(o)
                    ).props('flat dense color=negative')
    
    def update_property_panel(self):
        """Update the properties panel for the selected object"""
        self.property_panel.clear()
        
        with self.property_panel:
            if self.selected_object is None:
                ui.label('No object selected').classes('text-grey')
                return
            
            scene_obj = self.objects[self.selected_object]
            obj_id = self.selected_object
            
            # Object name
            ui.label(f'Selected: {scene_obj.name}').classes('text-bold')
            ui.label(f'Type: {scene_obj.obj_type}').classes('text-caption')
            
            ui.separator()
            
            # Position
            ui.label('Position').classes('text-weight-medium')
            with ui.row().classes('w-full gap-2'):
                ui.number('X', value=scene_obj.x, step=0.1, format='%.2f',
                         on_change=lambda e, o=obj_id: self._set_position(o, 'x', e.value)).classes('w-20')
                ui.number('Y', value=scene_obj.y, step=0.1, format='%.2f',
                         on_change=lambda e, o=obj_id: self._set_position(o, 'y', e.value)).classes('w-20')
                ui.number('Z', value=scene_obj.z, step=0.1, format='%.2f',
                         on_change=lambda e, o=obj_id: self._set_position(o, 'z', e.value)).classes('w-20')
            
            ui.separator()
            
            # Scale
            ui.label('Scale').classes('text-weight-medium')
            with ui.row().classes('w-full gap-2'):
                ui.number('X', value=scene_obj.scale_x, step=0.1, min=0.1, format='%.2f',
                         on_change=lambda e, o=obj_id: self._set_scale(o, 'x', e.value)).classes('w-20')
                ui.number('Y', value=scene_obj.scale_y, step=0.1, min=0.1, format='%.2f',
                         on_change=lambda e, o=obj_id: self._set_scale(o, 'y', e.value)).classes('w-20')
                ui.number('Z', value=scene_obj.scale_z, step=0.1, min=0.1, format='%.2f',
                         on_change=lambda e, o=obj_id: self._set_scale(o, 'z', e.value)).classes('w-20')
            
            # Uniform scale slider
            ui.label('Uniform Scale').classes('text-caption')
            ui.slider(min=0.1, max=5, step=0.1, value=1.0,
                     on_change=lambda e, o=obj_id: self._set_uniform_scale(o, e.value)).classes('w-full')
            
            ui.separator()
            
            # Rotation
            ui.label('Rotation (degrees)').classes('text-weight-medium')
            with ui.column().classes('w-full gap-1'):
                ui.slider(min=0, max=360, step=1, value=scene_obj.rot_x,
                         on_change=lambda e, o=obj_id: self._set_rotation(o, 'x', e.value)).classes('w-full')
                ui.label('X-axis').classes('text-caption')
                
                ui.slider(min=0, max=360, step=1, value=scene_obj.rot_y,
                         on_change=lambda e, o=obj_id: self._set_rotation(o, 'y', e.value)).classes('w-full')
                ui.label('Y-axis').classes('text-caption')
                
                ui.slider(min=0, max=360, step=1, value=scene_obj.rot_z,
                         on_change=lambda e, o=obj_id: self._set_rotation(o, 'z', e.value)).classes('w-full')
                ui.label('Z-axis').classes('text-caption')
            
            ui.separator()
            
            # Color (only for non-model objects)
            if not scene_obj.obj_type.startswith('model:'):
                ui.label('Color').classes('text-weight-medium')
                ui.color_input(value=scene_obj.color,
                              on_change=lambda e, o=obj_id: self._set_color(o, e.value)).classes('w-full')
                ui.separator()
            
            # Delete button
            ui.button('Delete Object', on_click=lambda o=obj_id: self.remove_object(o),
                     icon='delete').classes('w-full').props('color=negative')
    
    def _set_position(self, obj_id: str, axis: str, value: float):
        """Set position for an axis"""
        if obj_id not in self.objects or value is None:
            return
        scene_obj = self.objects[obj_id]
        setattr(scene_obj, axis, value)
        self.update_object(obj_id)
    
    def _set_scale(self, obj_id: str, axis: str, value: float):
        """Set scale for an axis"""
        if obj_id not in self.objects or value is None:
            return
        scene_obj = self.objects[obj_id]
        setattr(scene_obj, f'scale_{axis}', value)
        self.update_object(obj_id)
    
    def _set_uniform_scale(self, obj_id: str, value: float):
        """Set uniform scale for all axes"""
        if obj_id not in self.objects or value is None:
            return
        scene_obj = self.objects[obj_id]
        scene_obj.scale_x = value
        scene_obj.scale_y = value
        scene_obj.scale_z = value
        self.update_object(obj_id)
        self.update_property_panel()  # Update the individual scale inputs
    
    def _set_rotation(self, obj_id: str, axis: str, value: float):
        """Set rotation for an axis (in degrees)"""
        if obj_id not in self.objects or value is None:
            return
        scene_obj = self.objects[obj_id]
        import math
        radians = math.radians(value)
        setattr(scene_obj, f'rot_{axis}', radians)
        self.update_object(obj_id)
    
    def _set_color(self, obj_id: str, value: str):
        """Set the color of an object"""
        if obj_id not in self.objects or value is None:
            return
        scene_obj = self.objects[obj_id]
        scene_obj.color = value
        # Don't update if selected (keep highlight color)
        if obj_id != self.selected_object:
            scene_obj.obj.material(value)
    
    def clear_scene(self):
        """Remove all objects from the scene"""
        for obj_id in list(self.objects.keys()):
            scene_obj = self.objects[obj_id]
            scene_obj.obj.delete()
        self.objects.clear()
        self.selected_object = None
        self.object_counter = 0
        self.update_object_list()
        self.update_property_panel()
        ui.notify('Scene cleared')
    
    async def handle_model_upload(self, e: events.UploadEventArguments):
        """Handle uploaded GLB model"""
        filename = e.file.name
        if not filename.lower().endswith('.glb'):
            ui.notify('Only .glb files are supported!')
            return
        
        # Generate unique filename to avoid conflicts
        base_name = Path(filename).stem
        unique_filename = f"{base_name}_{uuid.uuid4().hex[:6]}.glb"
        file_path = UPLOAD_DIR / unique_filename
        
        # Save the file
        content = await e.file.read()
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # Create model entry
        model_id = str(uuid.uuid4())[:8]
        self.model_counter += 1
        self.uploaded_models[model_id] = UploadedModel(
            id=model_id,
            name=base_name,
            filename=unique_filename,
            url=f'/models/{unique_filename}'
        )
        
        self.update_model_list()
        ui.notify(f'Uploaded model: {base_name}')
    
    def update_model_list(self):
        """Update the list of uploaded models"""
        if self.model_list is None:
            return
            
        self.model_list.clear()
        
        with self.model_list:
            if not self.uploaded_models:
                ui.label('No models uploaded').classes('text-grey text-caption')
                return
            
            for model_id, model in self.uploaded_models.items():
                with ui.row().classes('w-full items-center gap-1'):
                    ui.button(
                        model.name,
                        on_click=lambda m=model_id: self.add_object(f'model:{m}'),
                        icon='add'
                    ).classes('flex-grow').props('flat dense')
                    ui.button(
                        icon='delete',
                        on_click=lambda m=model_id: self.remove_model(m)
                    ).props('flat dense color=negative')
    
    def remove_model(self, model_id: str):
        """Remove an uploaded model"""
        if model_id not in self.uploaded_models:
            return
        
        model = self.uploaded_models[model_id]
        
        # Check if any scene objects use this model
        using_model = [obj for obj in self.objects.values() if obj.model_id == model_id]
        if using_model:
            ui.notify(f'Cannot delete: {len(using_model)} object(s) in scene use this model')
            return
        
        # Delete the file
        file_path = UPLOAD_DIR / model.filename
        if file_path.exists():
            file_path.unlink()
        
        del self.uploaded_models[model_id]
        self.update_model_list()
        ui.notify(f'Removed model: {model.name}')


# Create and run the application
builder = SceneBuilder()
builder.create_ui()
ui.run(title='3D Scene Builder', port=8080)