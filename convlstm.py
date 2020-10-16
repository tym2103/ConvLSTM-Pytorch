'''
Date: 2020/08/30
@author: KimUyen
# The code was revised from repo: https://github.com/ndrplz/ConvLSTM_pytorch
'''
import torch.nn as nn
import torch
import math

class ConvLSTMCell(nn.Module):

    def __init__(self, input_dim, hidden_dim, kernel_size, stride, 
                 padding, cnn_dropout, rnn_dropout, bias=True, peephole=False,
                 batch_norm=False, layer_norm=False):
        """
        Initialize ConvLSTM cell.
        Parameters
        ----------
        input_dim: int
            Number of channels of input tensor.
        hidden_dim: int
            Number of channels of hidden state.
        kernel_size: (int, int)
            Size of the convolutional kernel for both cnn and rnn.
        stride, padding: (int, int)
            Stride and padding for convolutional input tensor.
        cnn_dropout, rnn_dropout: float
            cnn_dropout: dropout rate for convolutional input.
            rnn_dropout: dropout rate for convolutional state.
        bias: bool
            Whether or not to add the bias.
        peephole: bool
            add connection between cell state to gates
        batch_norm, linear_norm: bool
            add batch normalization or 
        """

        super(ConvLSTMCell, self).__init__()

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim

        self.kernel_size = kernel_size
        self.padding = padding
        self.stride = stride
        self.bias = bias
        self.peephole = peephole
        self.batch_norm = batch_norm
        self.layer_norm = layer_norm
        
        self.conv = nn.Conv2d(in_channels=self.input_dim,
                              out_channels=self.hidden_dim,
                              kernel_size=self.kernel_size,
                              stride = self.stride,
                              padding=self.padding,
                              bias=self.bias)
        self.rnn_conv = nn.Conv2d(self.hidden_dim, out_channels=self.hidden_dim, 
                                  kernel_size = self.kernel_size,
                                  padding=(math.floor(self.kernel_size[0]/2), 
                                         math.floor(self.kernel_size[1]/2)),
                                  bias=self.bias)

        self.cnn_dropout = nn.Dropout(cnn_dropout)
        self.rnn_dropout = nn.Dropout(rnn_dropout)
        
        self.batch_norm_2d = nn.BatchNorm2d(self.hidden_dim)
        self.layer_norm_x = nn.LayerNorm([4, 4], elementwise_affine=False)
        self.layer_norm_h = nn.LayerNorm([4, 4], elementwise_affine=False)
        
    def forward(self, input_tensor, cur_state):
        h_cur, c_cur = cur_state

        x = self.cnn_dropout(input_tensor)
        x_i = self.conv(x)
        x_f = self.conv(x)
        x_c = self.conv(x)
        x_o = self.conv(x)
        
        if self.batch_norm is True:
            x_i = self.batch_norm_2d(x_i)
            x_f = self.batch_norm_2d(x_f)
            x_c = self.batch_norm_2d(x_c)
            x_o = self.batch_norm_2d(x_o)
        
        h = self.rnn_dropout(h_cur)
        h_i = self.rnn_conv(h)
        h_f = self.rnn_conv(h)
        h_c = self.rnn_conv(h)
        h_o = self.rnn_conv(h)
        
        c = self.rnn_dropout(c_cur)
        c_i = self.rnn_conv(c)
        c_f = self.rnn_conv(c)
        c_o = self.rnn_conv(c)
        
        
        if self.layer_norm is True:
            x_i = self.layer_norm_x(x_i)
            x_f = self.layer_norm_x(x_f)
            x_c = self.layer_norm_x(x_c)
            x_o = self.layer_norm_x(x_o)
            h_i = self.layer_norm_h(h_i)
            h_f = self.layer_norm_h(h_f)
            h_c = self.layer_norm_h(h_c)
            h_o = self.layer_norm_h(h_o)
            
        if self.peephole is True:
            f = torch.sigmoid((x_f + h_f) + c_f * c)
            i = torch.sigmoid((x_i + h_i) + c_i * c)
        else:
            f = torch.sigmoid((x_f + h_f))
            i = torch.sigmoid((x_i + h_i))
        
        
        g = torch.tanh((x_c + h_c))
        c_next = f * c + i * g
        if self.peephole is True:
            o = torch.sigmoid(x_o + h_o + c_o * c)
        else:
            o = torch.sigmoid((x_o + h_o))
        h_next = o * torch.tanh(c_next)

        return h_next, c_next

    def init_hidden(self, batch_size, image_size):
        height = int((image_size[0] - self.kernel_size[0] + 2*self.padding[0])/self.stride[0] + 1)
        width = int((image_size[1] - self.kernel_size[1] + 2*self.padding[1])/self.stride[1] + 1)
        #height, width = image_size
        return (torch.zeros(batch_size, self.hidden_dim, height, width, device=self.conv.weight.device),
                torch.zeros(batch_size, self.hidden_dim, height, width, device=self.conv.weight.device))


class ConvLSTM(nn.Module):

    """
    Parameters:
        input_dim: Number of channels in input
        hidden_dim: Number of hidden channels
        kernel_size: Size of kernel in convolutions
        stride, padding: (int, int)
            Stride and padding for convolutional input tensor.
        cnn_dropout, rnn_dropout: float
            cnn_dropout: dropout rate for convolutional input.
            rnn_dropout: dropout rate for convolutional state.
        batch_first: Whether or not dimension 0 is the batch or not
        bias: Bias or no bias in Convolution
        return_sequence: return output sequence or final output only
        bidirectional: bool
            bidirectional ConvLSTM
    Input:
        A tensor of size B, T, C, H, W or T, B, C, H, W
    Output:
        A tuple of two sequences output and state
    Example:
        >> x = torch.rand((32, 10, 64, 128, 128))
        >> convlstm = ConvLSTM(input_dim=64, hidden_dim=16, kernel_size=(3, 3), 
                               stride=(1, 1), padding=(1, 1), cnn_dropout = 0.2,
                               rnn_dropout=0.2, batch_first=True, bias=False)
        >> output, last_state = convlstm(x)
    """

    def __init__(self, input_dim, hidden_dim, kernel_size, stride, padding, 
                 cnn_dropout=0.5, rnn_dropout=0.5,  
                 batch_first=False, bias=True, peephole=False, batch_norm=False,
                 layer_norm=False,
                 return_sequence=True,
                 bidirectional=False):
        super(ConvLSTM, self).__init__()

        print(kernel_size)
        self.batch_first = batch_first
        self.return_sequence = return_sequence
        self.bidirectional = bidirectional
        
        cell_list = ConvLSTMCell(input_dim=input_dim,
                                hidden_dim=hidden_dim,
                                kernel_size=kernel_size,
                                stride = stride,
                                padding = padding,
                                cnn_dropout=cnn_dropout,
                                rnn_dropout=rnn_dropout,
                                bias=bias,
                                peephole=peephole,
                                batch_norm=batch_norm,
                                layer_norm=layer_norm)

        self.cell_list = cell_list
        

    def forward(self, input_tensor, hidden_state=None):
        """
        Parameters
        ----------
        input_tensor: todo
            5-D Tensor either of shape (t, b, c, h, w) or (b, t, c, h, w)
        hidden_state: todo
            None. todo implement stateful
        Returns
        -------
        layer_output, last_state
        """
        if not self.batch_first:
            # (t, b, c, h, w) -> (b, t, c, h, w)
            input_tensor = input_tensor.permute(1, 0, 2, 3, 4)

        b, seq_len, _, h, w = input_tensor.size()

        # Implement stateful ConvLSTM
        if hidden_state is not None:
            raise NotImplementedError()
        else:
            # Since the init is done in forward. Can send image size here
            hidden_state = self._init_hidden(batch_size=b,
                                             image_size=(h, w))
            if self.bidirectional is True:
                hidden_state_inv = self._init_hidden(batch_size=b,
                                                     image_size=(h, w))

        ## LSTM forward direction
        input_fw = input_tensor
        h, c = hidden_state
        output_inner = []
        for t in range(seq_len):
            h, c = self.cell_list(input_tensor=input_fw[:, t, :, :, :],
                                             cur_state=[h, c])
            
            output_inner.append(h)
        output_inner = torch.stack((output_inner), dim=1)
        layer_output = output_inner
        last_state = [h, c]
        ####################
        
        
        ## LSTM inverse direction
        if self.bidirectional is True:
            input_inv = input_tensor
            h_inv, c_inv = hidden_state_inv
            output_inv = []
            for t in range(seq_len-1, -1, -1):
                h_inv, c_inv = self.cell_list(input_tensor=input_inv[:, t, :, :, :],
                                                 cur_state=[h_inv, c_inv])
                
                output_inv.append(h_inv)
            output_inv.reverse() 
            output_inv = torch.stack((output_inv), dim=1)
            layer_output = torch.cat((output_inner, output_inv), dim=2)
            last_state_inv = [h_inv, c_inv]
        ###################################
        
        return layer_output if self.return_sequence is True else layer_output[:, -1:], last_state, last_state_inv if self.bidirectional is True else None

    def _init_hidden(self, batch_size, image_size):
        init_states = self.cell_list.init_hidden(batch_size, image_size)
        return init_states