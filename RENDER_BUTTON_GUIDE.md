# Render Button Feature Documentation

## Overview
The Dash app now includes a manual render button that gives users complete control over when visualizations are generated. This improves performance and user experience by avoiding automatic re-rendering on every control change.

## How It Works

### 1. **Initial State**
- When the app first loads, you'll see an empty plot with instructions
- The render button shows "🚀 Render Visualization"
- No data processing occurs until you click the button

### 2. **Control Selection**
- Algorithm: Choose between PZWAV and AMICO
- Show Polygons: Toggle polygon fill display
- Show MER Tiles: Toggle MER tile overlay
- The button text updates to reflect your current selections

### 3. **Manual Rendering**
- Click the render button to generate the visualization
- The button shows "🔄 Re-render [Algorithm] (with/without polygons + MER tiles)"
- A loading spinner appears during data processing
- Status information shows render completion time

## Benefits

### **Performance Control**
- No automatic re-rendering on control changes
- Users decide when to trigger expensive operations
- Large datasets can be handled more efficiently

### **Better User Experience**
- Clear feedback on current settings
- Visual indication of render status
- Time stamp of last successful render

### **Resource Management**
- Prevents accidental multiple renders
- Reduces server load from frequent updates
- Allows users to batch setting changes

## Usage Examples

### **Basic Workflow**
1. Select algorithm: PZWAV or AMICO
2. Choose display options (polygons, MER tiles)
3. Click "Render Visualization"
4. Interact with the generated plot (zoom, pan, hover)
5. Change settings as needed
6. Click "Re-render" to update

### **Advanced Usage**
- **Algorithm Comparison**: Render PZWAV, then switch to AMICO and re-render
- **Performance Testing**: Toggle complex features (MER tiles) and compare render times
- **Data Exploration**: Use different polygon settings to focus on specific aspects

## Technical Implementation

### **Callback Structure**
```python
@app.callback(
    [Output('cluster-plot', 'figure'), Output('status-info', 'children')],
    [Input('render-button', 'n_clicks')],
    [State('algorithm-dropdown', 'value'),
     State('polygon-switch', 'value'),
     State('mer-switch', 'value')]
)
```

### **Button Text Updates**
- Dynamic button text based on current settings
- Clear indication of what will be rendered
- Visual feedback for user selections

### **Status Information**
- Algorithm and data counts
- Render completion timestamp
- Error handling with clear messages

## Troubleshooting

### **First Render Fails**
- Check EDEN environment activation
- Verify data file availability
- Review error messages in status panel

### **Slow Rendering**
- Large datasets take time to process
- MER tiles significantly increase render time
- Consider disabling complex features for initial exploration

### **Button Not Responding**
- Wait for current render to complete
- Check browser console for errors
- Restart the app if needed

## Comparison with Previous Behavior

| Feature | Auto-Render (Old) | Manual Render (New) |
|---------|------------------|-------------------|
| **Control** | Automatic updates | User-triggered |
| **Performance** | Can be slow/laggy | Optimized |
| **Feedback** | Immediate but jarring | Clear and controlled |
| **Resource Usage** | High (frequent renders) | Low (on-demand) |
| **User Experience** | Reactive | Intentional |

The render button transforms the Dash app from a reactive interface to an intentional, performance-optimized tool that gives users complete control over the visualization generation process.
