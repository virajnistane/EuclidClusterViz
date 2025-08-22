"""
Tests for UI and core modules.

Tests the UI layout generation and core application functionality.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add the source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cluster_visualization'))

try:
    from ui.layout import AppLayout
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False

try:
    from core.app import ClusterVisualizationCore
    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False


class TestAppLayout(unittest.TestCase):
    """Test cases for AppLayout class"""
    
    def setUp(self):
        """Set up test fixtures"""
        if not UI_AVAILABLE:
            self.skipTest("UI layout not available")
    
    def test_create_layout(self):
        """Test layout creation"""
        layout = AppLayout.create_layout()
        
        self.assertIsNotNone(layout)
        # Layout should be a Dash component
        self.assertTrue(hasattr(layout, 'children'))
    
    def test_create_algorithm_section(self):
        """Test algorithm selection section creation"""
        section = AppLayout._create_algorithm_section()
        
        self.assertIsNotNone(section)
        self.assertTrue(hasattr(section, 'children'))
        
        # Should contain a dropdown with PZWAV and AMICO options
        # This would require deeper inspection of the component tree
        # For now, just verify it creates something
        self.assertIsNotNone(section)
    
    def test_create_snr_section(self):
        """Test SNR filtering section creation"""
        section = AppLayout._create_snr_section()
        
        self.assertIsNotNone(section)
        self.assertTrue(hasattr(section, 'children'))
    
    def test_create_display_options_section(self):
        """Test display options section creation"""
        section = AppLayout._create_display_options_section()
        
        self.assertIsNotNone(section)
        self.assertTrue(hasattr(section, 'children'))
    
    def test_create_mer_controls_section(self):
        """Test MER controls section creation"""
        section = AppLayout._create_mer_controls_section()
        
        self.assertIsNotNone(section)
        self.assertTrue(hasattr(section, 'children'))
    
    def test_create_main_render_section(self):
        """Test main render section creation"""
        section = AppLayout._create_main_render_section()
        
        self.assertIsNotNone(section)
        self.assertTrue(hasattr(section, 'children'))


class TestClusterVisualizationCore(unittest.TestCase):
    """Test cases for ClusterVisualizationCore class"""
    
    def setUp(self):
        """Set up test fixtures"""
        if not CORE_AVAILABLE:
            self.skipTest("Core module not available")
            
        self.mock_app = MagicMock()
        self.core = ClusterVisualizationCore(self.mock_app)
    
    def test_core_initialization(self):
        """Test core initialization"""
        self.assertIsNotNone(self.core)
        self.assertEqual(self.core.app, self.mock_app)
    
    @patch('webbrowser.open')
    @patch('threading.Thread')
    def test_open_browser(self, mock_thread, mock_webbrowser):
        """Test browser opening functionality"""
        self.core.open_browser(port=8051, delay=0.1)
        
        # Should create a thread for delayed browser opening
        mock_thread.assert_called_once()
        
        # Get the thread target function and call it to test webbrowser.open
        thread_args = mock_thread.call_args
        target_function = thread_args[1]['target']  # keyword argument 'target'
        
        # Call the target function to simulate thread execution
        target_function()
        
        # Should call webbrowser.open with correct URL
        mock_webbrowser.assert_called_once_with('http://localhost:8051')
    
    def test_run_basic(self):
        """Test basic run functionality"""
        with patch.object(self.core, 'open_browser') as mock_open_browser:
            with patch('builtins.print'):  # Suppress print output
                # Mock the app.run_server to avoid actually starting a server
                self.mock_app.run_server = MagicMock()
                
                self.core.run(host='localhost', port=8050, debug=False, auto_open=True, external_access=False)
                
                # Should call open_browser when auto_open is True
                mock_open_browser.assert_called_once_with(8050)
                
                # Should call app.run_server with correct parameters
                self.mock_app.run_server.assert_called_once_with(
                    host='localhost',
                    port=8050,
                    debug=False,
                    dev_tools_hot_reload=False,
                    dev_tools_ui=False,
                    dev_tools_props_check=False
                )
    
    def test_run_external_access(self):
        """Test run with external access"""
        with patch.object(self.core, 'open_browser') as mock_open_browser:
            with patch('builtins.print'):  # Suppress print output
                self.mock_app.run_server = MagicMock()
                
                self.core.run(host='localhost', port=8050, debug=False, auto_open=True, external_access=True)
                
                # Should not call open_browser when external_access is True
                mock_open_browser.assert_not_called()
                
                # Should call app.run_server with host='0.0.0.0'
                call_args = self.mock_app.run_server.call_args
                self.assertEqual(call_args[1]['host'], '0.0.0.0')
    
    def test_run_no_auto_open(self):
        """Test run without auto-opening browser"""
        with patch.object(self.core, 'open_browser') as mock_open_browser:
            with patch('builtins.print'):  # Suppress print output
                self.mock_app.run_server = MagicMock()
                
                self.core.run(auto_open=False)
                
                # Should not call open_browser when auto_open is False
                mock_open_browser.assert_not_called()
    
    def test_try_multiple_ports_success(self):
        """Test trying multiple ports when first succeeds"""
        with patch.object(self.core, 'run') as mock_run:
            mock_run.return_value = None  # Simulate successful run
            
            self.core.try_multiple_ports(ports=[8050, 8051, 8052])
            
            # Should only call run once (first port succeeds)
            mock_run.assert_called_once_with(port=8050)
    
    def test_try_multiple_ports_address_in_use(self):
        """Test trying multiple ports when first is busy"""
        with patch.object(self.core, 'run') as mock_run:
            # First call raises "Address already in use", second succeeds
            mock_run.side_effect = [
                OSError("Address already in use"),
                None  # Second call succeeds
            ]
            
            with patch('builtins.print'):  # Suppress print output
                self.core.try_multiple_ports(ports=[8050, 8051, 8052])
            
            # Should call run twice (first fails, second succeeds)
            self.assertEqual(mock_run.call_count, 2)
            
            # Check the port arguments
            calls = mock_run.call_args_list
            self.assertEqual(calls[0][1]['port'], 8050)
            self.assertEqual(calls[1][1]['port'], 8051)
    
    def test_try_multiple_ports_other_error(self):
        """Test trying multiple ports with non-address error"""
        with patch.object(self.core, 'run') as mock_run:
            # Raise a different OSError that should be re-raised
            mock_run.side_effect = OSError("Some other error")
            
            with self.assertRaises(OSError) as context:
                self.core.try_multiple_ports(ports=[8050, 8051, 8052])
            
            self.assertIn("Some other error", str(context.exception))
            
            # Should only call run once before re-raising
            mock_run.assert_called_once()
    
    @patch('sys.argv', ['script.py', '--external'])
    def test_check_command_line_args_external(self):
        """Test command line argument checking for external access"""
        result = ClusterVisualizationCore.check_command_line_args()
        self.assertTrue(result)
    
    @patch('sys.argv', ['script.py', '--remote'])
    def test_check_command_line_args_remote(self):
        """Test command line argument checking for remote access"""
        result = ClusterVisualizationCore.check_command_line_args()
        self.assertTrue(result)
    
    @patch('sys.argv', ['script.py'])
    def test_check_command_line_args_none(self):
        """Test command line argument checking with no special args"""
        result = ClusterVisualizationCore.check_command_line_args()
        self.assertFalse(result)


class TestIntegration(unittest.TestCase):
    """Integration tests for UI and core modules"""
    
    def test_layout_and_core_compatibility(self):
        """Test that layout and core modules can work together"""
        if not UI_AVAILABLE or not CORE_AVAILABLE:
            self.skipTest("UI or Core modules not available")
        
        # Test that layout can be created
        layout = AppLayout.create_layout()
        self.assertIsNotNone(layout)
        
        # Test that core can be initialized
        mock_app = MagicMock()
        core = ClusterVisualizationCore(mock_app)
        self.assertIsNotNone(core)
        
        # Test that they can be used together
        # This would typically be done in the main application initialization
        mock_app.layout = layout
        self.assertEqual(mock_app.layout, layout)


if __name__ == '__main__':
    unittest.main()
