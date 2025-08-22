"""
Figure management module for cluster visualization.

This module handles figure configuration, layout settings,
and aspect ratio management for Plotly figures.
"""

import plotly.graph_objs as go
from typing import Dict, Any, Optional, Tuple


class FigureManager:
    """Handles Plotly figure configuration and layout management."""
    
    def __init__(self):
        """Initialize FigureManager."""
        pass
    
    def create_figure(self, traces: list, algorithm: str, free_aspect_ratio: bool = True,
                     relayout_data: Optional[Dict] = None) -> go.Figure:
        """
        Create a Plotly figure with traces and appropriate layout.
        
        Args:
            traces: List of Plotly traces to add to the figure
            algorithm: Algorithm name for title
            free_aspect_ratio: Whether to use free or equal aspect ratio
            relayout_data: Current zoom state to preserve
            
        Returns:
            Configured Plotly Figure object
        """
        fig = go.Figure(traces)
        
        # Configure aspect ratio
        xaxis_config, yaxis_config = self._get_axis_config(free_aspect_ratio)
        
        # Apply layout
        fig.update_layout(
            title=f'Cluster Detection Visualization - {algorithm}',
            xaxis_title='Right Ascension (degrees)',
            yaxis_title='Declination (degrees)',
            legend=dict(
                title='Legend',
                orientation='v',
                xanchor='left',
                x=1.01,
                yanchor='top',
                y=1,
                font=dict(size=10)
            ),
            hovermode='closest',
            margin=dict(l=40, r=120, t=60, b=40),
            xaxis=xaxis_config,
            yaxis=yaxis_config,
            autosize=True
        )
        
        # Preserve zoom state if available
        if relayout_data:
            self._apply_zoom_state(fig, relayout_data)
        
        return fig
    
    def create_empty_figure(self, free_aspect_ratio: bool = True, show_initial_message: bool = True) -> go.Figure:
        """
        Create an empty figure for initial state.
        
        Args:
            free_aspect_ratio: Whether to use free or equal aspect ratio
            show_initial_message: Whether to show the initial instruction message
            
        Returns:
            Empty Plotly Figure with appropriate layout
        """
        fig = go.Figure()
        
        # Configure aspect ratio
        xaxis_config, yaxis_config = self._get_axis_config(free_aspect_ratio, visible=not show_initial_message)
        
        layout_config = {
            'title': '',
            'margin': dict(l=40, r=20, t=40, b=40),
            'xaxis': xaxis_config,
            'yaxis': yaxis_config,
            'autosize': True,
            'showlegend': False
        }
        
        if show_initial_message:
            layout_config['annotations'] = [
                dict(
                    text="Select your preferred algorithm and display options from the sidebar,<br>"
                         "then click the 'Initial Render' button to generate the plot.",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, xanchor='center', yanchor='middle',
                    showarrow=False,
                    font=dict(size=16, color="gray")
                )
            ]
        
        fig.update_layout(**layout_config)
        return fig
    
    def create_empty_phz_figure(self) -> go.Figure:
        """Create an empty PHZ PDF plot for initial state."""
        fig = go.Figure()
        
        fig.update_layout(
            title='',
            xaxis_title='',
            yaxis_title='',
            margin=dict(l=40, r=20, t=20, b=40),
            showlegend=False,
            annotations=[
                dict(
                    text="Click on a CATRED data point above to view its PHZ_PDF",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, xanchor='center', yanchor='middle',
                    showarrow=False,
                    font=dict(size=14, color="gray")
                )
            ]
        )
        
        return fig
    
    def _get_axis_config(self, free_aspect_ratio: bool, visible: bool = True) -> Tuple[Dict, Dict]:
        """
        Get axis configuration based on aspect ratio setting.
        
        Args:
            free_aspect_ratio: Whether to use free or equal aspect ratio
            visible: Whether axes should be visible
            
        Returns:
            Tuple of (xaxis_config, yaxis_config)
        """
        if free_aspect_ratio:
            # Free aspect ratio - no constraints, better for zooming
            xaxis_config = dict(visible=visible)
            yaxis_config = dict(visible=visible)
        else:
            # Equal aspect ratio - astronomical accuracy
            xaxis_config = dict(
                scaleanchor="y",
                scaleratio=1,
                constrain="domain",
                visible=visible
            )
            yaxis_config = dict(
                constrain="domain",
                visible=visible
            )
        
        return xaxis_config, yaxis_config
    
    def _setup_layout(self, fig: go.Figure, algorithm: str) -> None:
        """Set up the figure layout with title and axis labels."""
        fig.update_layout(
            title=f'Cluster Visualization - {algorithm}',
            xaxis_title='Right Ascension (degrees)',
            yaxis_title='Declination (degrees)',
            hovermode='closest',
            margin=dict(l=40, r=20, t=40, b=40),
            autosize=True,
            showlegend=True,
            legend=dict(
                title='Legend',
                orientation='v',
                xanchor='left',
                x=1.01,
                yanchor='top',
                y=1
            )
        )

    def preserve_zoom_state(self, fig: go.Figure, relayout_data: Dict = None, current_figure: go.Figure = None) -> None:
        """
        Preserve and apply zoom state to figure.
        
        Args:
            fig: Figure to apply zoom state to
            relayout_data: Zoom state data from relayout events
            current_figure: Fallback figure to extract zoom state from if relayout_data is insufficient
        """
        if relayout_data and self._has_valid_zoom_data(relayout_data):
            self._apply_zoom_state(fig, relayout_data)
        elif current_figure:
            # Fallback: extract zoom from current figure
            self._extract_and_apply_zoom_from_figure(fig, current_figure)
    
    def _has_valid_zoom_data(self, relayout_data: Dict) -> bool:
        """Check if relayout_data contains valid zoom information."""
        if not relayout_data:
            return False
        
        has_x_zoom = ('xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data) or 'xaxis.range' in relayout_data
        has_y_zoom = ('yaxis.range[0]' in relayout_data and 'yaxis.range[1]' in relayout_data) or 'yaxis.range' in relayout_data
        
        return has_x_zoom or has_y_zoom
    
    def _extract_and_apply_zoom_from_figure(self, fig: go.Figure, current_figure) -> None:
        """Extract zoom state from current figure and apply to new figure."""
        if not current_figure:
            return
            
        # Handle both go.Figure objects and dict representations
        if hasattr(current_figure, 'layout'):
            # It's a go.Figure object
            layout = current_figure.layout
        elif isinstance(current_figure, dict) and 'layout' in current_figure:
            # It's a dict representation
            layout = current_figure['layout']
        else:
            return
            
        # Extract X-axis range
        if hasattr(layout, 'xaxis') and hasattr(layout.xaxis, 'range') and layout.xaxis.range:
            fig.update_xaxes(range=layout.xaxis.range)
        elif isinstance(layout, dict) and 'xaxis' in layout and 'range' in layout['xaxis']:
            fig.update_xaxes(range=layout['xaxis']['range'])
        
        # Extract Y-axis range
        if hasattr(layout, 'yaxis') and hasattr(layout.yaxis, 'range') and layout.yaxis.range:
            fig.update_yaxes(range=layout.yaxis.range)
        elif isinstance(layout, dict) and 'yaxis' in layout and 'range' in layout['yaxis']:
            fig.update_yaxes(range=layout['yaxis']['range'])

    def _apply_zoom_state(self, fig: go.Figure, relayout_data: Dict) -> None:
        """Apply saved zoom state to figure."""
        # Apply X-axis zoom
        if 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
            fig.update_xaxes(range=[relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']])
        elif 'xaxis.range' in relayout_data:
            fig.update_xaxes(range=relayout_data['xaxis.range'])
        
        # Apply Y-axis zoom
        if 'yaxis.range[0]' in relayout_data and 'yaxis.range[1]' in relayout_data:
            fig.update_yaxes(range=[relayout_data['yaxis.range[0]'], relayout_data['yaxis.range[1]']])
        elif 'yaxis.range' in relayout_data:
            fig.update_yaxes(range=relayout_data['yaxis.range'])
